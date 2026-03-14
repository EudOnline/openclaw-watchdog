from __future__ import annotations

import difflib
import json
import shutil
from datetime import datetime
from pathlib import Path

from openclaw_watchdog import generation_runtime
from openclaw_watchdog import guard_runtime


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
        baseline_data = json.loads(baseline.read_text(encoding='utf-8'))
        current_data = json.loads(current.read_text(encoding='utf-8'))
        diff_lines: list[str] = []
        walk_json_diff(current_data, baseline_data, '', diff_lines, limit=20)
        lines = ['current -> last-good JSON diff summary']
        if not diff_lines:
            lines.append('(no semantic difference detected)')
        else:
            lines.extend(f'- {line}' for line in diff_lines[:20])
    except (json.JSONDecodeError, FileNotFoundError):
        current_text = current.read_text(encoding='utf-8', errors='replace') if current.exists() else ''
        baseline_text = baseline.read_text(encoding='utf-8', errors='replace') if baseline.exists() else ''
        diff = list(
            difflib.unified_diff(
                current_text.splitlines(),
                baseline_text.splitlines(),
                fromfile=str(current),
                tofile=str(baseline),
                lineterm='',
            )
        )
        lines = ['current config is not valid JSON; fallback to text diff summary', *diff[:80]]
    summary_file.write_text('\n'.join(lines) + '\n', encoding='utf-8')
    engine.ctx.rollback_summary = '\n'.join(lines[:40]).strip()
    engine.log('WARN', f'rollback summary saved: {summary_file}')


def prune_rollback_archives(engine) -> None:
    import re

    stamps: set[str] = set()
    pattern = re.compile(r'^(?:openclaw\.broken|rollback-summary)\.(\d{8}-\d{6})\..*$')
    for path in engine.config.watchdog_rollback_archive_dir.glob('*'):
        match = pattern.match(path.name)
        if match:
            stamps.add(match.group(1))
    all_stamps = sorted(stamps, reverse=True)
    for stamp in all_stamps[engine.config.watchdog_keep_rollbacks :]:
        for suffix in (
            engine.config.watchdog_rollback_archive_dir / f'openclaw.broken.{stamp}.json',
            engine.config.watchdog_rollback_archive_dir / f'rollback-summary.{stamp}.txt',
        ):
            suffix.unlink(missing_ok=True)
        engine.log('INFO', f'pruned rollback archive timestamp={stamp}')


def restore_last_good(engine, *, reason: str = '') -> bool:
    candidates = generation_runtime.last_good_candidates(engine)
    if not candidates:
        return False

    rollback_ts = datetime.now().strftime('%Y%m%d-%H%M%S')
    broken_copy = engine.config.watchdog_rollback_archive_dir / f'openclaw.broken.{rollback_ts}.json'
    summary_archive = engine.config.watchdog_rollback_archive_dir / f'rollback-summary.{rollback_ts}.txt'
    current_config_existed = engine.config.openclaw_config.exists()
    current_fingerprint = generation_runtime.config_fingerprint(engine.config.openclaw_config) if current_config_existed else ''
    guard_before = guard_runtime.protected_paths_snapshot(engine.config)
    guard_runtime.record_guard_event(
        engine.config,
        operation='restore-last-good',
        phase='before',
        before=guard_before,
        context={'reason': reason or 'last-good-rollback'},
    )

    for candidate in candidates:
        candidate_path = Path(str(candidate.get('path', '') or ''))
        candidate_id = str(candidate.get('generation_id', '') or candidate_path.name)
        if not candidate_path.exists() or generation_runtime.load_json_file(candidate_path) is None:
            engine.log('WARN', f'skipping unusable last-good candidate generation={candidate_id} path={candidate_path}')
            continue

        drift_detected = bool(current_fingerprint and current_fingerprint != str(candidate.get('fingerprint', '') or ''))
        protected_drift_detected = bool(getattr(getattr(engine, 'ctx', None), 'config_drift_detected', False) or drift_detected)
        if current_config_existed:
            capture_rollback_summary(engine, engine.config.openclaw_config, candidate_path)
            summary_text = engine.config.watchdog_last_rollback_summary_file.read_text(encoding='utf-8')
            summary_prefix = [
                f'rollback_candidate={candidate_id}',
                f"rollback_reason={reason or 'last-good-rollback'}",
                f'candidate_path={candidate_path}',
                f"candidate_validated_at={candidate.get('validated_at', '')}",
                f"config_drift_detected={'true' if protected_drift_detected else 'false'}",
                '',
            ]
            engine.config.watchdog_last_rollback_summary_file.write_text(
                '\n'.join(summary_prefix) + summary_text,
                encoding='utf-8',
            )
            shutil.copy2(engine.config.openclaw_config, broken_copy)
            shutil.copy2(engine.config.watchdog_last_rollback_summary_file, summary_archive)
        else:
            message = '\n'.join(
                [
                    f'rollback_candidate={candidate_id}',
                    f"rollback_reason={reason or 'last-good-rollback'}",
                    f'candidate_path={candidate_path}',
                    f"candidate_validated_at={candidate.get('validated_at', '')}",
                    'current config file missing; no rollback diff available',
                ]
            )
            engine.config.watchdog_last_rollback_summary_file.write_text(message + '\n', encoding='utf-8')
            shutil.copy2(engine.config.watchdog_last_rollback_summary_file, summary_archive)
            engine.ctx.rollback_summary = message.strip()

        engine.config.openclaw_config.parent.mkdir(parents=True, exist_ok=True)
        if candidate_path.resolve() != engine.config.openclaw_config.resolve():
            shutil.copy2(candidate_path, engine.config.openclaw_config)
        if candidate_path.resolve() != engine.config.watchdog_last_good_config.resolve():
            shutil.copy2(candidate_path, engine.config.watchdog_last_good_config)
        restored_protected_paths = generation_runtime.restore_archived_protected_paths(engine, candidate)
        engine.ctx.rollback_occurred = True
        engine.ctx.rollback_summary_archive_file = str(summary_archive)
        engine.ctx.rollback_broken_config_file = str(broken_copy) if current_config_existed else ''
        engine.ctx.rollback_candidate_used = candidate_id
        engine.ctx.rollback_reason = reason or 'last-good-rollback'
        engine.ctx.config_drift_detected = protected_drift_detected
        engine.ctx.last_good_validated_at = str(candidate.get('validated_at', '') or '')
        engine.ctx.last_good_generation_id = candidate_id
        engine.ctx.last_good_generation_count = len(candidates)

        manifest = generation_runtime.load_last_good_manifest(engine)
        manifest['current_generation'] = candidate_id
        manifest['validated_at'] = str(candidate.get('validated_at', manifest.get('validated_at', '')) or manifest.get('validated_at', ''))
        generation_runtime.save_last_good_manifest(engine, generation_runtime.prune_last_good_generations(engine, manifest))
        guard_after = guard_runtime.protected_paths_snapshot(engine.config)
        guard_runtime.record_guard_event(
            engine.config,
            operation='restore-last-good',
            phase='after',
            before=guard_before,
            after=guard_after,
            validation=f'candidate={candidate_id}',
            context={
                'reason': reason or 'last-good-rollback',
                'restored_protected_paths': restored_protected_paths,
            },
        )
        prune_rollback_archives(engine)
        engine.log(
            'WARN',
            f"restored config from last-good snapshot generation={candidate_id}; restored_paths={','.join(restored_protected_paths) if restored_protected_paths else 'openclaw_config'}; broken copy: {broken_copy}; rollback summary archive: {summary_archive}",
        )
        return True
    return False
