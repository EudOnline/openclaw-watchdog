from __future__ import annotations

import hashlib
import json
import shutil
from datetime import datetime
from pathlib import Path

from openclaw_watchdog import guard_runtime


def load_json_file(path: Path) -> object | None:
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def config_fingerprint(path: Path) -> str:
    if not path.exists() or not path.is_file():
        return ''
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _generation_file(engine, generation_id: str) -> Path:
    return engine.config.watchdog_rollback_archive_dir / f'last-good.{generation_id}.json'


def _normalized_generation(entry: object) -> dict[str, object] | None:
    if not isinstance(entry, dict):
        return None
    generation_id = str(entry.get('generation_id', '') or '').strip()
    path = str(entry.get('path', '') or '').strip()
    if not generation_id or not path:
        return None
    return {
        'generation_id': generation_id,
        'path': path,
        'fingerprint': str(entry.get('fingerprint', '') or ''),
        'validated_at': str(entry.get('validated_at', '') or ''),
        'conversation_ready': bool(entry.get('conversation_ready', False)),
        'minimal_usable_ready': bool(entry.get('minimal_usable_ready', False)),
        'summary': str(entry.get('summary', '') or ''),
        'health_level': str(entry.get('health_level', 'unknown') or 'unknown'),
        'protected_paths': [
            normalized
            for normalized in (guard_runtime._normalized_protected_path(item) for item in entry.get('protected_paths', []))
            if normalized is not None
        ]
        if isinstance(entry.get('protected_paths', []), list)
        else [],
    }


def load_last_good_manifest(engine) -> dict[str, object]:
    manifest_path = engine.config.watchdog_last_good_manifest_file
    payload = load_json_file(manifest_path)
    generations: list[dict[str, object]] = []
    if isinstance(payload, dict):
        for item in payload.get('generations', []):
            normalized = _normalized_generation(item)
            if normalized is not None:
                generations.append(normalized)
    return {
        'current_generation': str((payload or {}).get('current_generation', '') or '') if isinstance(payload, dict) else '',
        'current_file': str((payload or {}).get('current_file', engine.config.watchdog_last_good_config) or engine.config.watchdog_last_good_config)
        if isinstance(payload, dict)
        else str(engine.config.watchdog_last_good_config),
        'validated_at': str((payload or {}).get('validated_at', '') or '') if isinstance(payload, dict) else '',
        'generations': generations,
    }


def save_last_good_manifest(engine, manifest: dict[str, object]) -> None:
    engine.config.watchdog_last_good_manifest_file.parent.mkdir(parents=True, exist_ok=True)
    engine.config.watchdog_last_good_manifest_file.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + '\n',
        encoding='utf-8',
    )


def _protected_archive_root(engine, generation_id: str) -> Path:
    return engine.config.watchdog_rollback_archive_dir / f'protected.{generation_id}'


def _protected_archive_token(label: str) -> str:
    cleaned = ''.join(ch if ch.isalnum() else '_' for ch in label.strip())
    return cleaned.strip('_') or 'protected_path'


def prune_last_good_generations(engine, manifest: dict[str, object]) -> dict[str, object]:
    generations = [item for item in manifest.get('generations', []) if isinstance(item, dict)]
    keep = max(1, engine.config.watchdog_last_good_generations)
    kept = generations[:keep]
    manifest['generations'] = kept
    active_names = {Path(str(item.get('path', ''))).name for item in kept if str(item.get('path', '')).strip()}
    active_protected_dirs = {
        _protected_archive_root(engine, str(item.get('generation_id', '') or '')).name
        for item in kept
        if str(item.get('generation_id', '') or '').strip()
    }
    for path in engine.config.watchdog_rollback_archive_dir.glob('last-good.*.json'):
        if path.name not in active_names:
            path.unlink(missing_ok=True)
    for path in engine.config.watchdog_rollback_archive_dir.glob('protected.*'):
        if path.name in active_protected_dirs:
            continue
        if path.is_dir():
            shutil.rmtree(path, ignore_errors=True)
        else:
            path.unlink(missing_ok=True)
    return manifest


def last_good_candidates(engine) -> list[dict[str, object]]:
    manifest = load_last_good_manifest(engine)
    return [item for item in manifest.get('generations', []) if isinstance(item, dict)]


def last_good_status(engine) -> dict[str, object]:
    manifest = load_last_good_manifest(engine)
    candidates = last_good_candidates(engine)
    current_generation = str(manifest.get('current_generation', '') or '')
    current = next((item for item in candidates if str(item.get('generation_id', '')) == current_generation), None)
    if current is None and candidates:
        current = candidates[0]
    current = current or {}
    return {
        'last_good_config_exists': engine.config.watchdog_last_good_config.exists(),
        'last_good_manifest_exists': engine.config.watchdog_last_good_manifest_file.exists(),
        'last_good_validated_at': str(current.get('validated_at', manifest.get('validated_at', '')) or manifest.get('validated_at', '')),
        'last_good_generation_id': str(current.get('generation_id', current_generation) or current_generation),
        'last_good_generation_count': len(candidates),
        'last_good_current_file': str(current.get('path', engine.config.watchdog_last_good_config) or engine.config.watchdog_last_good_config),
    }


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
        normalized = guard_runtime._normalized_protected_path(item)
        if normalized is None:
            continue
        path = Path(str(normalized.get('path', '') or ''))
        archive_path = ''
        if path == engine.config.openclaw_config:
            archive_path = str(generation_file)
        elif path.exists():
            target = archive_root / _protected_archive_token(str(normalized.get('label', path.name) or path.name))
            target.parent.mkdir(parents=True, exist_ok=True)
            if path.is_dir():
                shutil.copytree(path, target)
            elif path.is_file():
                shutil.copy2(path, target)
            archive_path = str(target)
        normalized['archive_path'] = archive_path
        archived.append(normalized)
    return archived


def restore_archived_protected_paths(engine, candidate: dict[str, object]) -> list[str]:
    restored: list[str] = []
    for item in candidate.get('protected_paths', []):
        normalized = guard_runtime._normalized_protected_path(item)
        if normalized is None:
            continue
        label = str(normalized.get('label', '') or '')
        if label == 'openclaw_config':
            continue
        archive_raw = str(normalized.get('archive_path', '') or '')
        if not archive_raw:
            continue
        archive_path = Path(archive_raw)
        if not archive_path.exists():
            continue
        target = Path(str(normalized.get('path', '') or ''))
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
    if getattr(getattr(engine, 'ctx', None), 'survival_mode_active', False):
        engine.log('INFO', 'skipping last-good snapshot refresh while survival mode is active')
        return
    if not engine.config.openclaw_config.exists():
        return
    validated_at = engine.now_iso()
    fingerprint = config_fingerprint(engine.config.openclaw_config)
    conversation_ready = bool((validation or {}).get('conversation_ready', False))
    minimal_usable_ready = bool((validation or {}).get('minimal_usable_ready', conversation_ready))
    summary = str((validation or {}).get('conversation_probe_summary', '') or '')
    health_level = str((validation or {}).get('health_level', 'healthy') or 'healthy')
    protected_paths = guard_runtime.protected_paths_snapshot(engine.config)

    manifest = load_last_good_manifest(engine)
    generations = [item for item in manifest.get('generations', []) if isinstance(item, dict)]
    existing = next((item for item in generations if str(item.get('fingerprint', '')) == fingerprint and fingerprint), None)
    if existing is not None:
        generation_id = str(existing.get('generation_id', '') or '')
        archive_path = Path(str(existing.get('path', '') or ''))
        if not generation_id:
            generation_id = datetime.now().strftime('%Y%m%d-%H%M%S')
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
            'generation_id': generation_id,
            'path': str(archive_path),
            'fingerprint': fingerprint,
            'validated_at': validated_at,
            'conversation_ready': conversation_ready,
            'minimal_usable_ready': minimal_usable_ready,
            'summary': summary,
            'health_level': health_level,
            'protected_paths': protected_paths,
        }
        generations = [item for item in generations if str(item.get('generation_id', '')) != generation_id]
        generations.insert(0, entry)
    else:
        generation_id = datetime.now().strftime('%Y%m%d-%H%M%S')
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
                'generation_id': generation_id,
                'path': str(archive_path),
                'fingerprint': fingerprint,
                'validated_at': validated_at,
                'conversation_ready': conversation_ready,
                'minimal_usable_ready': minimal_usable_ready,
                'summary': summary,
                'health_level': health_level,
                'protected_paths': protected_paths,
            },
        )

    engine.config.watchdog_last_good_config.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(engine.config.openclaw_config, engine.config.watchdog_last_good_config)

    manifest['current_generation'] = generation_id
    manifest['current_file'] = str(engine.config.watchdog_last_good_config)
    manifest['validated_at'] = validated_at
    manifest['generations'] = generations
    manifest = prune_last_good_generations(engine, manifest)
    save_last_good_manifest(engine, manifest)

    engine.ctx.last_good_validated_at = validated_at
    engine.ctx.last_good_generation_id = generation_id
    engine.ctx.last_good_generation_count = len(manifest.get('generations', []))
    engine.log(
        'INFO',
        f'updated last-good config snapshot: {engine.config.watchdog_last_good_config} generation={generation_id}',
    )
