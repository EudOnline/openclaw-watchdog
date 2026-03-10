from __future__ import annotations

import difflib
import hashlib
import json
import os
import shutil
import signal
import time
from datetime import datetime
from pathlib import Path


def run_doctor(engine) -> tuple[int, str]:
    result = engine.run_command(
        ["openclaw", "doctor", "--non-interactive"],
        timeout=engine.config.watchdog_doctor_timeout_seconds,
        merge_stderr=True,
    )
    return result.returncode, result.output


def config_invalid(engine, doctor_output: str) -> bool:
    return "Config invalid" in doctor_output


def _load_json_file(path: Path) -> object | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def _config_fingerprint(path: Path) -> str:
    if not path.exists() or not path.is_file():
        return ""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fingerprint_path(path: Path) -> str:
    if not path.exists():
        return ""
    if path.is_file():
        return hashlib.sha256(path.read_bytes()).hexdigest()
    if path.is_dir():
        digest = hashlib.sha256()
        for child in sorted(item for item in path.rglob("*") if item.is_file()):
            digest.update(str(child.relative_to(path)).encode("utf-8", errors="replace"))
            digest.update(b"\0")
            digest.update(hashlib.sha256(child.read_bytes()).digest())
        return digest.hexdigest()
    return ""


def _normalized_protected_path(entry: object) -> dict[str, object] | None:
    if not isinstance(entry, dict):
        return None
    path = str(entry.get("path", "") or "").strip()
    if not path:
        return None
    return {
        "label": str(entry.get("label", Path(path).name) or Path(path).name),
        "path": path,
        "exists": bool(entry.get("exists", False)),
        "kind": str(entry.get("kind", "missing") or "missing"),
        "fingerprint": str(entry.get("fingerprint", "") or ""),
        "archive_path": str(entry.get("archive_path", "") or ""),
    }


def _guard_manifest_default() -> dict[str, object]:
    return {
        "events": [],
        "latest_snapshot": [],
    }


def _protected_label(config, path: Path) -> str:
    if path == config.openclaw_config:
        return "openclaw_config"
    if config.env_file is not None and path == config.env_file:
        return "env_file"
    if path == config.openclaw_config.parent / "extensions":
        return "openclaw_extensions"
    if path == config.watchdog_survival_config_file:
        return "watchdog_survival_config"
    return path.name or str(path)


def protected_paths_snapshot(config) -> list[dict[str, object]]:
    paths: list[Path] = []
    seen: set[str] = set()

    def add(path: Path | None) -> None:
        if path is None:
            return
        token = str(path)
        if token in seen:
            return
        seen.add(token)
        paths.append(path)

    add(config.openclaw_config)
    add(config.env_file)
    add(config.openclaw_config.parent / "extensions")
    add(config.watchdog_survival_config_file)
    for raw in config.watchdog_protected_paths:
        add(Path(raw).expanduser())

    snapshot: list[dict[str, object]] = []
    for path in paths:
        snapshot.append(
            {
                "label": _protected_label(config, path),
                "path": str(path),
                "exists": path.exists(),
                "kind": "directory" if path.is_dir() else "file" if path.is_file() else "missing",
                "fingerprint": fingerprint_path(path),
            }
        )
    return snapshot


def _snapshot_map(snapshot: list[dict[str, object]]) -> dict[str, dict[str, object]]:
    mapped: dict[str, dict[str, object]] = {}
    for item in snapshot:
        normalized = _normalized_protected_path(item)
        if normalized is None:
            continue
        mapped[str(normalized.get("path", ""))] = normalized
    return mapped


def diff_protected_snapshots(before: list[dict[str, object]], after: list[dict[str, object]]) -> list[dict[str, object]]:
    before_map = _snapshot_map(before)
    after_map = _snapshot_map(after)
    changes: list[dict[str, object]] = []
    for path in sorted(set(before_map) | set(after_map)):
        before_item = before_map.get(path)
        after_item = after_map.get(path)
        if before_item is None and after_item is not None:
            if (
                not bool(after_item.get("exists", False))
                and str(after_item.get("kind", "missing") or "missing") == "missing"
                and not str(after_item.get("fingerprint", "") or "")
            ):
                continue
            changes.append({"label": after_item.get("label", Path(path).name), "path": path, "change": "added"})
            continue
        if before_item is not None and after_item is None:
            changes.append({"label": before_item.get("label", Path(path).name), "path": path, "change": "removed"})
            continue
        assert before_item is not None and after_item is not None
        if (
            bool(before_item.get("exists", False)) != bool(after_item.get("exists", False))
            or str(before_item.get("kind", "")) != str(after_item.get("kind", ""))
            or str(before_item.get("fingerprint", "")) != str(after_item.get("fingerprint", ""))
        ):
            changes.append({"label": after_item.get("label", before_item.get("label", Path(path).name)), "path": path, "change": "modified"})
    return changes


def load_guard_manifest(config) -> dict[str, object]:
    payload = _load_json_file(config.watchdog_guard_manifest_file)
    manifest = _guard_manifest_default()
    if not isinstance(payload, dict):
        return manifest
    events = payload.get("events", [])
    manifest["events"] = [item for item in events if isinstance(item, dict)] if isinstance(events, list) else []
    latest = payload.get("latest_snapshot", [])
    manifest["latest_snapshot"] = [item for item in latest if _normalized_protected_path(item) is not None] if isinstance(latest, list) else []
    return manifest


def save_guard_manifest(config, manifest: dict[str, object]) -> None:
    config.watchdog_guard_manifest_file.parent.mkdir(parents=True, exist_ok=True)
    config.watchdog_guard_manifest_file.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def record_guard_event(
    config,
    *,
    operation: str,
    phase: str,
    before: list[dict[str, object]] | None = None,
    after: list[dict[str, object]] | None = None,
    validation: str = "",
    context: dict[str, object] | None = None,
) -> dict[str, object]:
    manifest = load_guard_manifest(config)
    effective_snapshot = after if after is not None else before if before is not None else protected_paths_snapshot(config)
    changes = diff_protected_snapshots(before or [], after or []) if before is not None and after is not None else []
    labels = [str(item.get("label", Path(str(item.get("path", ""))).name)) for item in changes]
    summary_parts = [phase, operation]
    if labels:
        summary_parts.append("changed=" + ",".join(labels))
    if validation:
        summary_parts.append("validation=" + validation)
    event = {
        "time": datetime.now().astimezone().isoformat(timespec="seconds"),
        "operation": operation,
        "phase": phase,
        "summary": " | ".join(summary_parts),
        "validation": validation,
        "changes": changes,
        "snapshot": effective_snapshot,
        "context": context or {},
    }
    manifest["events"] = [event, *[item for item in manifest.get("events", []) if isinstance(item, dict)]][:20]
    manifest["latest_snapshot"] = effective_snapshot
    save_guard_manifest(config, manifest)
    return event


def guard_status(config) -> dict[str, object]:
    manifest = load_guard_manifest(config)
    latest = next((item for item in manifest.get("events", []) if isinstance(item, dict)), {})
    return {
        "guard_manifest_file": str(config.watchdog_guard_manifest_file),
        "guard_last_operation": str(latest.get("operation", "") or ""),
        "guard_last_phase": str(latest.get("phase", "") or ""),
        "guard_last_time": str(latest.get("time", "") or ""),
        "guard_last_summary": str(latest.get("summary", "") or ""),
    }


def _generation_file(engine, generation_id: str) -> Path:
    return engine.config.watchdog_rollback_archive_dir / f"last-good.{generation_id}.json"


def _normalized_generation(entry: object) -> dict[str, object] | None:
    if not isinstance(entry, dict):
        return None
    generation_id = str(entry.get("generation_id", "") or "").strip()
    path = str(entry.get("path", "") or "").strip()
    if not generation_id or not path:
        return None
    return {
        "generation_id": generation_id,
        "path": path,
        "fingerprint": str(entry.get("fingerprint", "") or ""),
        "validated_at": str(entry.get("validated_at", "") or ""),
        "conversation_ready": bool(entry.get("conversation_ready", False)),
        "minimal_usable_ready": bool(entry.get("minimal_usable_ready", False)),
        "summary": str(entry.get("summary", "") or ""),
        "health_level": str(entry.get("health_level", "unknown") or "unknown"),
        "protected_paths": [
            normalized
            for normalized in (_normalized_protected_path(item) for item in entry.get("protected_paths", []))
            if normalized is not None
        ]
        if isinstance(entry.get("protected_paths", []), list)
        else [],
    }


def load_last_good_manifest(engine) -> dict[str, object]:
    manifest_path = engine.config.watchdog_last_good_manifest_file
    payload = _load_json_file(manifest_path)
    generations: list[dict[str, object]] = []
    if isinstance(payload, dict):
        for item in payload.get("generations", []):
            normalized = _normalized_generation(item)
            if normalized is not None:
                generations.append(normalized)
    return {
        "current_generation": str((payload or {}).get("current_generation", "") or "") if isinstance(payload, dict) else "",
        "current_file": str((payload or {}).get("current_file", engine.config.watchdog_last_good_config) or engine.config.watchdog_last_good_config)
        if isinstance(payload, dict)
        else str(engine.config.watchdog_last_good_config),
        "validated_at": str((payload or {}).get("validated_at", "") or "") if isinstance(payload, dict) else "",
        "generations": generations,
    }


def save_last_good_manifest(engine, manifest: dict[str, object]) -> None:
    engine.config.watchdog_last_good_manifest_file.parent.mkdir(parents=True, exist_ok=True)
    engine.config.watchdog_last_good_manifest_file.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def prune_last_good_generations(engine, manifest: dict[str, object]) -> dict[str, object]:
    generations = [item for item in manifest.get("generations", []) if isinstance(item, dict)]
    keep = max(1, engine.config.watchdog_last_good_generations)
    kept = generations[:keep]
    manifest["generations"] = kept
    active_names = {Path(str(item.get("path", ""))).name for item in kept if str(item.get("path", "")).strip()}
    active_protected_dirs = {
        _protected_archive_root(engine, str(item.get("generation_id", "") or "")).name
        for item in kept
        if str(item.get("generation_id", "") or "").strip()
    }
    for path in engine.config.watchdog_rollback_archive_dir.glob("last-good.*.json"):
        if path.name not in active_names:
            path.unlink(missing_ok=True)
    for path in engine.config.watchdog_rollback_archive_dir.glob("protected.*"):
        if path.name in active_protected_dirs:
            continue
        if path.is_dir():
            shutil.rmtree(path, ignore_errors=True)
        else:
            path.unlink(missing_ok=True)
    return manifest


def last_good_candidates(engine) -> list[dict[str, object]]:
    manifest = load_last_good_manifest(engine)
    generations = [item for item in manifest.get("generations", []) if isinstance(item, dict)]
    if generations:
        return generations
    if engine.config.watchdog_last_good_config.exists():
        return [
            {
                "generation_id": "generation-0",
                "path": str(engine.config.watchdog_last_good_config),
                "fingerprint": _config_fingerprint(engine.config.watchdog_last_good_config),
                "validated_at": "",
                "conversation_ready": False,
                "minimal_usable_ready": False,
                "summary": "legacy single-file last-good snapshot",
                "health_level": "unknown",
                "protected_paths": protected_paths_snapshot(engine.config),
            }
        ]
    return []


def last_good_status(engine) -> dict[str, object]:
    manifest = load_last_good_manifest(engine)
    candidates = last_good_candidates(engine)
    current_generation = str(manifest.get("current_generation", "") or "")
    current = next((item for item in candidates if str(item.get("generation_id", "")) == current_generation), None)
    if current is None and candidates:
        current = candidates[0]
    current = current or {}
    return {
        "last_good_config_exists": engine.config.watchdog_last_good_config.exists(),
        "last_good_manifest_exists": engine.config.watchdog_last_good_manifest_file.exists(),
        "last_good_validated_at": str(current.get("validated_at", manifest.get("validated_at", "")) or manifest.get("validated_at", "")),
        "last_good_generation_id": str(current.get("generation_id", current_generation) or current_generation),
        "last_good_generation_count": len(candidates),
        "last_good_current_file": str(current.get("path", engine.config.watchdog_last_good_config) or engine.config.watchdog_last_good_config),
    }


def drift_context(engine) -> dict[str, object]:
    candidates = last_good_candidates(engine)
    if not candidates:
        return {
            "detected": False,
            "scope": [],
            "summary": "",
            "since_last_good": "",
        }
    baseline = candidates[0]
    baseline_generation = str(baseline.get("generation_id", "") or "")
    validated_at = str(baseline.get("validated_at", "") or "")
    baseline_snapshot = [item for item in baseline.get("protected_paths", []) if isinstance(item, dict)]
    if baseline_snapshot:
        changes = diff_protected_snapshots(baseline_snapshot, protected_paths_snapshot(engine.config))
        scope = [str(item.get("label", Path(str(item.get("path", ""))).name)) for item in changes]
    else:
        scope = []
        current_fingerprint = _config_fingerprint(engine.config.openclaw_config) if engine.config.openclaw_config.exists() else ""
        candidate_fingerprint = str(baseline.get("fingerprint", "") or "")
        if current_fingerprint and candidate_fingerprint and current_fingerprint != candidate_fingerprint:
            scope.append("openclaw_config")
    summary = "protected paths changed since last-good: " + ", ".join(scope) if scope else ""
    parts: list[str] = []
    if baseline_generation:
        parts.append(f"generation={baseline_generation}")
    if validated_at:
        parts.append(f"validated_at={validated_at}")
    return {
        "detected": bool(scope),
        "scope": scope,
        "summary": summary,
        "since_last_good": " ".join(parts),
    }


def config_drift_detected(engine) -> bool:
    return bool(drift_context(engine).get("detected", False))


def _protected_archive_root(engine, generation_id: str) -> Path:
    return engine.config.watchdog_rollback_archive_dir / f"protected.{generation_id}"


def _protected_archive_token(label: str) -> str:
    cleaned = "".join(ch if ch.isalnum() else "_" for ch in label.strip())
    return cleaned.strip("_") or "protected_path"


def archive_protected_paths(
    engine,
    *,
    generation_id: str,
    generation_file: Path,
    protected_paths: list[dict[str, object]],
) -> list[dict[str, object]]:
    archive_root = _protected_archive_root(engine, generation_id)
    if archive_root.exists():
        shutil.rmtree(archive_root, ignore_errors=True)

    archived: list[dict[str, object]] = []
    for item in protected_paths:
        normalized = _normalized_protected_path(item)
        if normalized is None:
            continue
        path = Path(str(normalized.get("path", "") or ""))
        archive_path = ""
        if path == engine.config.openclaw_config:
            archive_path = str(generation_file)
        elif path.exists():
            target = archive_root / _protected_archive_token(str(normalized.get("label", path.name) or path.name))
            target.parent.mkdir(parents=True, exist_ok=True)
            if path.is_dir():
                shutil.copytree(path, target)
            elif path.is_file():
                shutil.copy2(path, target)
            archive_path = str(target)
        normalized["archive_path"] = archive_path
        archived.append(normalized)
    return archived


def restore_archived_protected_paths(engine, candidate: dict[str, object]) -> list[str]:
    restored: list[str] = []
    for item in candidate.get("protected_paths", []):
        normalized = _normalized_protected_path(item)
        if normalized is None:
            continue
        label = str(normalized.get("label", "") or "")
        if label == "openclaw_config":
            continue
        archive_raw = str(normalized.get("archive_path", "") or "")
        if not archive_raw:
            continue
        archive_path = Path(archive_raw)
        if not archive_path.exists():
            continue
        target = Path(str(normalized.get("path", "") or ""))
        target.parent.mkdir(parents=True, exist_ok=True)
        if archive_path.is_dir():
            if target.exists() and target.is_file():
                target.unlink(missing_ok=True)
            if target.exists() and target.is_dir():
                shutil.rmtree(target, ignore_errors=True)
            shutil.copytree(archive_path, target)
        else:
            if target.exists() and target.is_dir():
                shutil.rmtree(target, ignore_errors=True)
            shutil.copy2(archive_path, target)
        restored.append(label or target.name)
    return restored


def backup_last_good(engine, *, validation: dict[str, object] | None = None) -> None:
    if getattr(engine, "survival_mode_active", False):
        engine.log("INFO", "skipping last-good snapshot refresh while survival mode is active")
        return
    if not engine.config.openclaw_config.exists():
        return
    validated_at = engine.now_iso()
    fingerprint = _config_fingerprint(engine.config.openclaw_config)
    conversation_ready = bool((validation or {}).get("conversation_ready", False))
    minimal_usable_ready = bool((validation or {}).get("minimal_usable_ready", conversation_ready))
    summary = str((validation or {}).get("conversation_probe_summary", "") or "")
    health_level = str((validation or {}).get("health_level", "healthy") or "healthy")
    protected_paths = protected_paths_snapshot(engine.config)

    manifest = load_last_good_manifest(engine)
    generations = [item for item in manifest.get("generations", []) if isinstance(item, dict)]
    existing = next((item for item in generations if str(item.get("fingerprint", "")) == fingerprint and fingerprint), None)
    if existing is not None:
        generation_id = str(existing.get("generation_id", "") or "")
        archive_path = Path(str(existing.get("path", "") or ""))
        if not generation_id:
            generation_id = datetime.now().strftime("%Y%m%d-%H%M%S")
            archive_path = _generation_file(engine, generation_id)
        if not archive_path.exists():
            archive_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(engine.config.openclaw_config, archive_path)
        protected_paths = archive_protected_paths(
            engine,
            generation_id=generation_id,
            generation_file=archive_path,
            protected_paths=protected_paths,
        )
        entry = {
            "generation_id": generation_id,
            "path": str(archive_path),
            "fingerprint": fingerprint,
            "validated_at": validated_at,
            "conversation_ready": conversation_ready,
            "minimal_usable_ready": minimal_usable_ready,
            "summary": summary,
            "health_level": health_level,
            "protected_paths": protected_paths,
        }
        generations = [item for item in generations if str(item.get("generation_id", "")) != generation_id]
        generations.insert(0, entry)
    else:
        generation_id = datetime.now().strftime("%Y%m%d-%H%M%S")
        archive_path = _generation_file(engine, generation_id)
        archive_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(engine.config.openclaw_config, archive_path)
        protected_paths = archive_protected_paths(
            engine,
            generation_id=generation_id,
            generation_file=archive_path,
            protected_paths=protected_paths,
        )
        generations.insert(
            0,
            {
                "generation_id": generation_id,
                "path": str(archive_path),
                "fingerprint": fingerprint,
                "validated_at": validated_at,
                "conversation_ready": conversation_ready,
                "minimal_usable_ready": minimal_usable_ready,
                "summary": summary,
                "health_level": health_level,
                "protected_paths": protected_paths,
            },
        )

    engine.config.watchdog_last_good_config.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(engine.config.openclaw_config, engine.config.watchdog_last_good_config)

    manifest["current_generation"] = generation_id
    manifest["current_file"] = str(engine.config.watchdog_last_good_config)
    manifest["validated_at"] = validated_at
    manifest["generations"] = generations
    manifest = prune_last_good_generations(engine, manifest)
    save_last_good_manifest(engine, manifest)

    engine.last_good_validated_at = validated_at
    engine.last_good_generation_id = generation_id
    engine.last_good_generation_count = len(manifest.get("generations", []))
    engine.log(
        "INFO",
        f"updated last-good config snapshot: {engine.config.watchdog_last_good_config} generation={generation_id}",
    )


def walk_json_diff(current, baseline, path: str, out: list[str], *, limit: int) -> None:
    if len(out) >= limit:
        return
    if current == baseline:
        return
    if isinstance(current, list) and isinstance(baseline, list):
        out.append(f"{path or '$'}: array changed ({len(current)} -> {len(baseline)})")
        return
    if isinstance(current, dict) and isinstance(baseline, dict):
        keys = sorted(set(current) | set(baseline))
        for key in keys:
            next_path = f"{path}.{key}" if path else key
            if key not in current:
                out.append(f"{next_path}: added")
            elif key not in baseline:
                out.append(f"{next_path}: removed")
            else:
                walk_json_diff(current[key], baseline[key], next_path, out, limit=limit)
            if len(out) >= limit:
                return
        return
    out.append(
        f"{path or '$'}: {json.dumps(current, ensure_ascii=False, sort_keys=True)} -> {json.dumps(baseline, ensure_ascii=False, sort_keys=True)}"
    )


def capture_rollback_summary(engine, current: Path, baseline: Path) -> None:
    summary_file = engine.config.watchdog_last_rollback_summary_file
    lines: list[str]
    try:
        baseline_data = json.loads(baseline.read_text(encoding="utf-8"))
        current_data = json.loads(current.read_text(encoding="utf-8"))
        diff_lines: list[str] = []
        walk_json_diff(current_data, baseline_data, "", diff_lines, limit=20)
        lines = ["current -> last-good JSON diff summary"]
        if not diff_lines:
            lines.append("(no semantic difference detected)")
        else:
            lines.extend(f"- {line}" for line in diff_lines[:20])
    except (json.JSONDecodeError, FileNotFoundError):
        current_text = current.read_text(encoding="utf-8", errors="replace") if current.exists() else ""
        baseline_text = baseline.read_text(encoding="utf-8", errors="replace") if baseline.exists() else ""
        diff = list(
            difflib.unified_diff(
                current_text.splitlines(),
                baseline_text.splitlines(),
                fromfile=str(current),
                tofile=str(baseline),
                lineterm="",
            )
        )
        lines = ["current config is not valid JSON; fallback to text diff summary", *diff[:80]]
    summary_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
    engine.rollback_summary = "\n".join(lines[:40]).strip()
    engine.log("WARN", f"rollback summary saved: {summary_file}")


def prune_rollback_archives(engine) -> None:
    import re

    stamps: set[str] = set()
    pattern = re.compile(r"^(?:openclaw\.broken|rollback-summary)\.(\d{8}-\d{6})\..*$")
    for path in engine.config.watchdog_rollback_archive_dir.glob("*"):
        match = pattern.match(path.name)
        if match:
            stamps.add(match.group(1))
    all_stamps = sorted(stamps, reverse=True)
    for stamp in all_stamps[engine.config.watchdog_keep_rollbacks :]:
        for suffix in (
            engine.config.watchdog_rollback_archive_dir / f"openclaw.broken.{stamp}.json",
            engine.config.watchdog_rollback_archive_dir / f"rollback-summary.{stamp}.txt",
        ):
            suffix.unlink(missing_ok=True)
        engine.log("INFO", f"pruned rollback archive timestamp={stamp}")


def run_pre_repair_backup(engine) -> None:
    if not engine.config.watchdog_enable_pre_repair_backup:
        engine.pre_repair_backup_result = "disabled"
        return
    if engine.incident_backup_marker.exists():
        engine.pre_repair_backup_result = "skipped-existing-incident-backup"
        return
    if not engine.config.watchdog_backup_script.exists():
        engine.pre_repair_backup_result = "backup-script-missing"
        engine.log("WARN", f"pre-repair backup skipped: missing script {engine.config.watchdog_backup_script}")
        engine.incident_backup_marker.write_text(f"{engine.run_ts} backup-script-missing\n", encoding="utf-8")
        return
    engine.log("INFO", f"running pre-repair backup via {engine.config.watchdog_backup_script}")
    result = engine.run_command(
        [
            "bash",
            "-lc",
            'source "$1" 2>/dev/null || true; node "$2"',
            "_",
            str(engine.config.watchdog_backup_env_file),
            str(engine.config.watchdog_backup_script),
        ],
        timeout=engine.config.watchdog_backup_timeout_seconds,
        merge_stderr=True,
    )
    with engine.config.watchdog_log_file.open("a", encoding="utf-8") as handle:
        if result.output:
            handle.write(result.output)
    if result.returncode == 0:
        engine.pre_repair_backup_result = "success"
        engine.log("INFO", "pre-repair backup completed")
    else:
        engine.pre_repair_backup_result = "failed"
        engine.log("WARN", "pre-repair backup failed; continuing remediation")
    engine.incident_backup_marker.write_text(f"{engine.run_ts} {engine.pre_repair_backup_result}\n", encoding="utf-8")


def restore_last_good(engine, *, reason: str = "") -> bool:
    candidates = last_good_candidates(engine)
    if not candidates:
        return False

    rollback_ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    broken_copy = engine.config.watchdog_rollback_archive_dir / f"openclaw.broken.{rollback_ts}.json"
    summary_archive = engine.config.watchdog_rollback_archive_dir / f"rollback-summary.{rollback_ts}.txt"
    current_config_existed = engine.config.openclaw_config.exists()
    current_fingerprint = _config_fingerprint(engine.config.openclaw_config) if current_config_existed else ""
    guard_before = protected_paths_snapshot(engine.config)
    record_guard_event(
        engine.config,
        operation="restore-last-good",
        phase="before",
        before=guard_before,
        context={"reason": reason or "last-good-rollback"},
    )

    for candidate in candidates:
        candidate_path = Path(str(candidate.get("path", "") or ""))
        candidate_id = str(candidate.get("generation_id", "") or candidate_path.name)
        if not candidate_path.exists() or _load_json_file(candidate_path) is None:
            engine.log("WARN", f"skipping unusable last-good candidate generation={candidate_id} path={candidate_path}")
            continue

        drift_detected = bool(current_fingerprint and current_fingerprint != str(candidate.get("fingerprint", "") or ""))
        protected_drift_detected = bool(getattr(engine, "config_drift_detected", False) or drift_detected)
        if current_config_existed:
            capture_rollback_summary(engine, engine.config.openclaw_config, candidate_path)
            summary_text = engine.config.watchdog_last_rollback_summary_file.read_text(encoding="utf-8")
            summary_prefix = [
                f"rollback_candidate={candidate_id}",
                f"rollback_reason={reason or 'last-good-rollback'}",
                f"candidate_path={candidate_path}",
                f"candidate_validated_at={candidate.get('validated_at', '')}",
                f"config_drift_detected={'true' if protected_drift_detected else 'false'}",
                "",
            ]
            engine.config.watchdog_last_rollback_summary_file.write_text(
                "\n".join(summary_prefix) + summary_text,
                encoding="utf-8",
            )
            shutil.copy2(engine.config.openclaw_config, broken_copy)
            shutil.copy2(engine.config.watchdog_last_rollback_summary_file, summary_archive)
        else:
            message = "\n".join(
                [
                    f"rollback_candidate={candidate_id}",
                    f"rollback_reason={reason or 'last-good-rollback'}",
                    f"candidate_path={candidate_path}",
                    f"candidate_validated_at={candidate.get('validated_at', '')}",
                    "current config file missing; no rollback diff available",
                ]
            )
            engine.config.watchdog_last_rollback_summary_file.write_text(message + "\n", encoding="utf-8")
            shutil.copy2(engine.config.watchdog_last_rollback_summary_file, summary_archive)
            engine.rollback_summary = message.strip()

        engine.config.openclaw_config.parent.mkdir(parents=True, exist_ok=True)
        if candidate_path.resolve() != engine.config.openclaw_config.resolve():
            shutil.copy2(candidate_path, engine.config.openclaw_config)
        if candidate_path.resolve() != engine.config.watchdog_last_good_config.resolve():
            shutil.copy2(candidate_path, engine.config.watchdog_last_good_config)
        restored_protected_paths = restore_archived_protected_paths(engine, candidate)
        engine.rollback_occurred = True
        engine.rollback_summary_archive_file = str(summary_archive)
        engine.rollback_broken_config_file = str(broken_copy) if current_config_existed else ""
        engine.rollback_candidate_used = candidate_id
        engine.rollback_reason = reason or "last-good-rollback"
        engine.config_drift_detected = protected_drift_detected
        engine.last_good_validated_at = str(candidate.get("validated_at", "") or "")
        engine.last_good_generation_id = candidate_id
        engine.last_good_generation_count = len(candidates)

        manifest = load_last_good_manifest(engine)
        manifest["current_generation"] = candidate_id
        manifest["validated_at"] = str(candidate.get("validated_at", manifest.get("validated_at", "")) or manifest.get("validated_at", ""))
        save_last_good_manifest(engine, prune_last_good_generations(engine, manifest))
        guard_after = protected_paths_snapshot(engine.config)
        record_guard_event(
            engine.config,
            operation="restore-last-good",
            phase="after",
            before=guard_before,
            after=guard_after,
            validation=f"candidate={candidate_id}",
            context={
                "reason": reason or "last-good-rollback",
                "restored_protected_paths": restored_protected_paths,
            },
        )
        prune_rollback_archives(engine)
        engine.log(
            "WARN",
            f"restored config from last-good snapshot generation={candidate_id}; restored_paths={','.join(restored_protected_paths) if restored_protected_paths else 'openclaw_config'}; broken copy: {broken_copy}; rollback summary archive: {summary_archive}",
        )
        return True
    return False


def kill_stray_listeners(engine, main_pid: str) -> None:
    killed = False
    for pid in engine.listener_pids():
        if pid == main_pid:
            continue
        result = engine.run_command(["ps", "-p", pid, "-o", "args="], timeout=10)
        cmdline = result.output.strip()
        if "openclaw" in cmdline.lower():
            engine.log("WARN", f"killing stray listener pid={pid} cmd={cmdline}")
            try:
                os.kill(int(pid), signal.SIGTERM)
            except (ProcessLookupError, PermissionError, ValueError):
                pass
            killed = True
    if killed:
        time.sleep(2)


def restart_service(engine) -> bool:
    engine.log("INFO", f"restarting {engine.config.openclaw_gateway_service}")
    engine.run_command(["systemctl", "--user", "reset-failed", engine.config.openclaw_gateway_service], timeout=15)
    result = engine.run_command(["systemctl", "--user", "restart", engine.config.openclaw_gateway_service], timeout=30)
    if result.returncode == 0:
        time.sleep(engine.config.watchdog_restart_wait_seconds)
        return True
    engine.log("WARN", f"failed to restart {engine.config.openclaw_gateway_service}: {result.output.strip()}")
    return False


def run_doctor_repair(engine) -> None:
    if not engine.config.watchdog_enable_doctor_repair:
        return
    engine.log("INFO", "running openclaw doctor --repair --non-interactive --yes")
    result = engine.run_command(
        ["openclaw", "doctor", "--repair", "--non-interactive", "--yes"],
        timeout=engine.config.watchdog_doctor_timeout_seconds,
        merge_stderr=True,
    )
    with engine.config.watchdog_log_file.open("a", encoding="utf-8") as handle:
        if result.output:
            handle.write(result.output)
    if result.returncode == 0:
        engine.log("INFO", "doctor repair completed")
    else:
        engine.log("WARN", f"doctor repair exited rc={result.returncode}")
