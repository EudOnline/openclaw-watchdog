from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path


def _load_json_file(path: Path) -> object | None:
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def fingerprint_path(path: Path) -> str:
    if not path.exists():
        return ''
    if path.is_file():
        return hashlib.sha256(path.read_bytes()).hexdigest()
    if path.is_dir():
        digest = hashlib.sha256()
        for child in sorted(item for item in path.rglob('*') if item.is_file()):
            digest.update(str(child.relative_to(path)).encode('utf-8', errors='replace'))
            digest.update(b'\0')
            digest.update(hashlib.sha256(child.read_bytes()).digest())
        return digest.hexdigest()
    return ''


def _normalized_protected_path(entry: object) -> dict[str, object] | None:
    if not isinstance(entry, dict):
        return None
    path = str(entry.get('path', '') or '').strip()
    if not path:
        return None
    return {
        'label': str(entry.get('label', '') or Path(path).name),
        'path': path,
        'exists': bool(entry.get('exists', False)),
        'kind': str(entry.get('kind', 'missing') or 'missing'),
        'fingerprint': str(entry.get('fingerprint', '') or ''),
        'archive_path': str(entry.get('archive_path', '') or ''),
    }


def _guard_manifest_default() -> dict[str, object]:
    return {
        'events': [],
        'latest_snapshot': [],
    }


def _protected_label(config, path: Path) -> str:
    if path == config.openclaw_config:
        return 'openclaw_config'
    if config.env_file is not None and path == config.env_file:
        return 'env_file'
    if path == config.openclaw_config.parent / 'extensions':
        return 'openclaw_extensions'
    if path == config.watchdog_survival_config_file:
        return 'watchdog_survival_config'
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
    add(config.openclaw_config.parent / 'extensions')
    add(config.watchdog_survival_config_file)
    for raw in config.watchdog_protected_paths:
        add(Path(raw).expanduser())

    snapshot: list[dict[str, object]] = []
    for path in paths:
        snapshot.append(
            {
                'label': _protected_label(config, path),
                'path': str(path),
                'exists': path.exists(),
                'kind': 'directory' if path.is_dir() else 'file' if path.is_file() else 'missing',
                'fingerprint': fingerprint_path(path),
            }
        )
    return snapshot


def _snapshot_map(snapshot: list[dict[str, object]]) -> dict[str, dict[str, object]]:
    mapped: dict[str, dict[str, object]] = {}
    for item in snapshot:
        normalized = _normalized_protected_path(item)
        if normalized is None:
            continue
        mapped[str(normalized.get('path', ''))] = normalized
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
                not bool(after_item.get('exists', False))
                and str(after_item.get('kind', 'missing') or 'missing') == 'missing'
                and not str(after_item.get('fingerprint', '') or '')
            ):
                continue
            changes.append({'label': after_item.get('label', Path(path).name), 'path': path, 'change': 'added'})
            continue
        if before_item is not None and after_item is None:
            changes.append({'label': before_item.get('label', Path(path).name), 'path': path, 'change': 'removed'})
            continue
        assert before_item is not None and after_item is not None
        if (
            bool(before_item.get('exists', False)) != bool(after_item.get('exists', False))
            or str(before_item.get('kind', '')) != str(after_item.get('kind', ''))
            or str(before_item.get('fingerprint', '')) != str(after_item.get('fingerprint', ''))
        ):
            changes.append({'label': after_item.get('label', before_item.get('label', Path(path).name)), 'path': path, 'change': 'modified'})
    return changes


def load_guard_manifest(config) -> dict[str, object]:
    payload = _load_json_file(config.watchdog_guard_manifest_file)
    manifest = _guard_manifest_default()
    if not isinstance(payload, dict):
        return manifest
    events = payload.get('events', [])
    manifest['events'] = [item for item in events if isinstance(item, dict)] if isinstance(events, list) else []
    latest = payload.get('latest_snapshot', [])
    manifest['latest_snapshot'] = [item for item in latest if _normalized_protected_path(item) is not None] if isinstance(latest, list) else []
    return manifest


def save_guard_manifest(config, manifest: dict[str, object]) -> None:
    config.watchdog_guard_manifest_file.parent.mkdir(parents=True, exist_ok=True)
    config.watchdog_guard_manifest_file.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + '\n',
        encoding='utf-8',
    )


def record_guard_event(
    config,
    *,
    operation: str,
    phase: str,
    before: list[dict[str, object]] | None = None,
    after: list[dict[str, object]] | None = None,
    validation: str = '',
    context: dict[str, object] | None = None,
) -> dict[str, object]:
    manifest = load_guard_manifest(config)
    effective_snapshot = after if after is not None else before if before is not None else protected_paths_snapshot(config)
    changes = diff_protected_snapshots(before or [], after or []) if before is not None and after is not None else []
    labels = [str(item.get('label', Path(str(item.get('path', ''))).name)) for item in changes]
    summary_parts = [phase, operation]
    if labels:
        summary_parts.append('changed=' + ','.join(labels))
    if validation:
        summary_parts.append('validation=' + validation)
    event = {
        'time': datetime.now().astimezone().isoformat(timespec='seconds'),
        'operation': operation,
        'phase': phase,
        'summary': ' | '.join(summary_parts),
        'validation': validation,
        'changes': changes,
        'snapshot': effective_snapshot,
        'context': context or {},
    }
    manifest['events'] = [event, *[item for item in manifest.get('events', []) if isinstance(item, dict)]][:20]
    manifest['latest_snapshot'] = effective_snapshot
    save_guard_manifest(config, manifest)
    return event


def guard_status(config) -> dict[str, object]:
    manifest = load_guard_manifest(config)
    latest = next((item for item in manifest.get('events', []) if isinstance(item, dict)), {})
    return {
        'guard_manifest_file': str(config.watchdog_guard_manifest_file),
        'guard_last_operation': str(latest.get('operation', '') or ''),
        'guard_last_phase': str(latest.get('phase', '') or ''),
        'guard_last_time': str(latest.get('time', '') or ''),
        'guard_last_summary': str(latest.get('summary', '') or ''),
    }
