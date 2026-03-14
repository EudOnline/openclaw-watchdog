from __future__ import annotations

from pathlib import Path

from openclaw_watchdog import generation_runtime
from openclaw_watchdog import guard_runtime


def fingerprint_path(path: Path) -> str:
    return guard_runtime.fingerprint_path(path)


def protected_paths_snapshot(config) -> list[dict[str, object]]:
    return guard_runtime.protected_paths_snapshot(config)


def diff_protected_snapshots(before: list[dict[str, object]], after: list[dict[str, object]]) -> list[dict[str, object]]:
    return guard_runtime.diff_protected_snapshots(before, after)


def load_guard_manifest(config) -> dict[str, object]:
    return guard_runtime.load_guard_manifest(config)


def save_guard_manifest(config, manifest: dict[str, object]) -> None:
    guard_runtime.save_guard_manifest(config, manifest)


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
    return guard_runtime.record_guard_event(
        config,
        operation=operation,
        phase=phase,
        before=before,
        after=after,
        validation=validation,
        context=context,
    )


def guard_status(config) -> dict[str, object]:
    return guard_runtime.guard_status(config)


def load_last_good_manifest(engine) -> dict[str, object]:
    return generation_runtime.load_last_good_manifest(engine)


def save_last_good_manifest(engine, manifest: dict[str, object]) -> None:
    generation_runtime.save_last_good_manifest(engine, manifest)


def prune_last_good_generations(engine, manifest: dict[str, object]) -> dict[str, object]:
    return generation_runtime.prune_last_good_generations(engine, manifest)


def last_good_candidates(engine) -> list[dict[str, object]]:
    return generation_runtime.last_good_candidates(engine)


def last_good_status(engine) -> dict[str, object]:
    return generation_runtime.last_good_status(engine)


def archive_protected_paths(
    engine,
    *,
    generation_id: str,
    generation_file: Path,
    protected_paths: list[dict[str, object]],
) -> list[dict[str, object]]:
    return generation_runtime.archive_protected_paths(
        engine,
        generation_id=generation_id,
        generation_file=generation_file,
        protected_paths=protected_paths,
    )


def restore_archived_protected_paths(engine, candidate: dict[str, object]) -> list[str]:
    return generation_runtime.restore_archived_protected_paths(engine, candidate)


def backup_last_good(engine, *, validation: dict[str, object] | None = None) -> None:
    generation_runtime.backup_last_good(engine, validation=validation)


def drift_context(engine) -> dict[str, object]:
    candidates = generation_runtime.last_good_candidates(engine)
    if not candidates:
        return {
            'detected': False,
            'scope': [],
            'summary': '',
            'since_last_good': '',
        }
    baseline = candidates[0]
    baseline_generation = str(baseline.get('generation_id', '') or '')
    validated_at = str(baseline.get('validated_at', '') or '')
    baseline_snapshot = [item for item in baseline.get('protected_paths', []) if isinstance(item, dict)]
    if baseline_snapshot:
        changes = guard_runtime.diff_protected_snapshots(baseline_snapshot, guard_runtime.protected_paths_snapshot(engine.config))
        scope = [str(item.get('label', Path(str(item.get('path', ''))).name)) for item in changes]
    else:
        scope = []
        current_fingerprint = generation_runtime.config_fingerprint(engine.config.openclaw_config) if engine.config.openclaw_config.exists() else ''
        candidate_fingerprint = str(baseline.get('fingerprint', '') or '')
        if current_fingerprint and candidate_fingerprint and current_fingerprint != candidate_fingerprint:
            scope.append('openclaw_config')
    summary = 'protected paths changed since last-good: ' + ', '.join(scope) if scope else ''
    parts: list[str] = []
    if baseline_generation:
        parts.append(f'generation={baseline_generation}')
    if validated_at:
        parts.append(f'validated_at={validated_at}')
    return {
        'detected': bool(scope),
        'scope': scope,
        'summary': summary,
        'since_last_good': ' '.join(parts),
    }


def apply_drift_context(engine, drift: dict[str, object] | None = None) -> dict[str, object]:
    payload = drift if isinstance(drift, dict) else drift_context(engine)
    ctx = getattr(engine, 'ctx', None)
    if ctx is not None:
        ctx.config_drift_detected = bool(payload.get('detected', False))
        ctx.drift_scope = [str(item) for item in payload.get('scope', []) if str(item).strip()]
        ctx.drift_since_last_good = str(payload.get('since_last_good', '') or '')
        ctx.drift_summary = str(payload.get('summary', '') or '')
    return payload


def config_drift_detected(engine) -> bool:
    return bool(drift_context(engine).get('detected', False))
