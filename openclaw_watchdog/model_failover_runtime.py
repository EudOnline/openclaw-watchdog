from __future__ import annotations

import json
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from openclaw_watchdog import engine_support_runtime
from openclaw_watchdog import file_ops
from openclaw_watchdog.openclaw_runtime import config_runtime

_STATUS_KEYS = (
    'status',
    'statusCode',
    'status_code',
    'http_status',
    'httpStatus',
    'response_status',
)
_MODEL_TEXT_HINTS = (
    'model',
    'provider',
    'upstream',
    'completion',
    'chat/completions',
    'llm',
)
_STATUS_PATTERNS = (
    re.compile(r'\bHTTP(?:/\d(?:\.\d)?)?\s+(\d{3})\b', re.IGNORECASE),
    re.compile(r'\b(?:status(?:code)?|http[_ ]status|response[_ ]status)\D{0,8}(\d{3})\b', re.IGNORECASE),
)


def _parse_datetime(value: object) -> datetime | None:
    text = str(value or '').strip()
    if not text:
        return None
    if text.endswith('Z'):
        text = text[:-1] + '+00:00'
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def _extract_datetime(payload: dict[str, object]) -> datetime | None:
    for key in ('timestamp', 'time', 'ts', 'datetime', 'created_at', 'at'):
        if key in payload:
            resolved = _parse_datetime(payload.get(key))
            if resolved is not None:
                return resolved
    return None


def _engine_now(engine) -> datetime:
    now_iso = getattr(engine, 'now_iso', None)
    if callable(now_iso):
        resolved = _parse_datetime(now_iso())
        if resolved is not None:
            return resolved
    resolved = _parse_datetime(engine_support_runtime.now_iso(engine))
    if resolved is not None:
        return resolved
    return datetime.now().astimezone()


def _read_run_state(engine) -> dict[str, object]:
    reader = getattr(engine, 'read_run_state', None)
    if not callable(reader):
        return {}
    payload = reader()
    return payload if isinstance(payload, dict) else {}


def _write_run_state(engine, updates: dict[str, object]) -> None:
    writer = getattr(engine, 'write_run_state', None)
    if callable(writer):
        writer(updates)


def _log(engine, level: str, message: str) -> None:
    logger = getattr(engine, 'log', None)
    if callable(logger):
        logger(level, message)


def _text_fields(payload: dict[str, object]) -> list[str]:
    values: list[str] = []
    for key in ('message', 'msg', 'summary', 'detail', 'error', 'event'):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            values.append(value)
    return values


def _event_text(payload: dict[str, object]) -> str:
    return ' '.join(_text_fields(payload)).strip()


def _extract_status_code(payload: dict[str, object]) -> int | None:
    for key in _STATUS_KEYS:
        value = payload.get(key)
        if isinstance(value, int):
            return value
        if isinstance(value, str) and value.strip().isdigit():
            return int(value.strip())
    for key in ('response', 'http', 'error'):
        value = payload.get(key)
        if isinstance(value, dict):
            nested = _extract_status_code(value)
            if nested is not None:
                return nested
    text = _event_text(payload)
    for pattern in _STATUS_PATTERNS:
        match = pattern.search(text)
        if match:
            return int(match.group(1))
    return None


def _looks_like_model_error(payload: dict[str, object], status_code: int) -> bool:
    if status_code == 200:
        return False
    if any(isinstance(payload.get(key), str) and str(payload.get(key)).strip() for key in ('model', 'provider')):
        return True
    lowered = _event_text(payload).lower()
    return any(token in lowered for token in _MODEL_TEXT_HINTS)


def _decode_json_events(text: str) -> list[dict[str, object]]:
    stripped = text.strip()
    if not stripped:
        return []
    if stripped.startswith('['):
        try:
            payload = json.loads(stripped)
        except json.JSONDecodeError:
            return []
        if isinstance(payload, list):
            return [item for item in payload if isinstance(item, dict)]
        return []
    events: list[dict[str, object]] = []
    for raw_line in stripped.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            payload = {'message': line}
        if isinstance(payload, dict):
            events.append(payload)
    return events


def _log_candidates(config) -> list[Path]:
    candidates: list[Path] = []
    config_log = config_runtime.read_logging_file_from_config(config.openclaw_config)
    if config_log is not None:
        candidates.append(config_log.expanduser())
    default_dir = Path('/tmp/openclaw')
    if default_dir.exists():
        candidates.extend(sorted(default_dir.glob('openclaw-*.log'), reverse=True)[:3])
    seen: set[Path] = set()
    ordered: list[Path] = []
    for candidate in candidates:
        resolved = candidate.expanduser()
        if resolved not in seen:
            seen.add(resolved)
            ordered.append(resolved)
    return ordered


def _read_tail(path: Path, *, max_bytes: int) -> str:
    with path.open('rb') as handle:
        handle.seek(0, 2)
        size = handle.tell()
        handle.seek(max(0, size - max_bytes))
        return handle.read().decode('utf-8', errors='replace')


def _read_command_events(engine) -> tuple[list[dict[str, object]], str]:
    result = engine.run_command(
        [
            'openclaw',
            'logs',
            '--json',
            '--limit',
            str(int(getattr(engine.config, 'watchdog_model_http_error_logs_limit', 200) or 200)),
        ],
        timeout=20,
        merge_stderr=True,
    )
    if result.returncode != 0:
        return [], 'command-unavailable'
    events = _decode_json_events(result.output)
    return events, 'openclaw-logs'


def _read_file_events(engine) -> tuple[list[dict[str, object]], str]:
    max_bytes = max(4096, int(getattr(engine.config, 'watchdog_model_http_error_log_max_bytes', 262144) or 262144))
    for candidate in _log_candidates(engine.config):
        if not candidate.exists() or not candidate.is_file():
            continue
        events = _decode_json_events(_read_tail(candidate, max_bytes=max_bytes))
        if events:
            return events, str(candidate)
    return [], 'no-log-file'


def _recent_model_http_error_events(engine) -> tuple[list[dict[str, object]], str]:
    command_events, source = _read_command_events(engine)
    events = command_events
    if not events:
        events, source = _read_file_events(engine)
    now = _engine_now(engine)
    window_minutes = max(1, int(getattr(engine.config, 'watchdog_model_http_error_window_minutes', 15) or 15))
    cutoff = now - timedelta(minutes=window_minutes)
    recent: list[dict[str, object]] = []
    for payload in events:
        event_time = _extract_datetime(payload)
        if event_time is None or event_time < cutoff:
            continue
        status_code = _extract_status_code(payload)
        if status_code is None or status_code == 200:
            continue
        if not _looks_like_model_error(payload, status_code):
            continue
        entry = dict(payload)
        entry['_status_code'] = status_code
        entry['_timestamp'] = event_time.isoformat(timespec='seconds')
        recent.append(entry)
    recent.sort(key=lambda item: str(item.get('_timestamp', '')))
    return recent, source


def _model_section(payload: dict[str, object]) -> dict[str, object]:
    agents = payload.get('agents')
    defaults = agents.get('defaults') if isinstance(agents, dict) else None
    model = defaults.get('model') if isinstance(defaults, dict) else None
    if not isinstance(model, dict):
        raise ValueError('OpenClaw config is missing agents.defaults.model')
    return model


def _normalized_fallbacks(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _cooldown_remaining_seconds(now: datetime, last_applied_at: str, cooldown_seconds: int) -> int:
    if cooldown_seconds <= 0:
        return 0
    last_applied = _parse_datetime(last_applied_at)
    if last_applied is None:
        return 0
    elapsed = int((now - last_applied).total_seconds())
    if elapsed >= cooldown_seconds:
        return 0
    return max(0, cooldown_seconds - elapsed)


def _recent_apply_history(run_state: dict[str, object], now: datetime) -> list[str]:
    cutoff = now - timedelta(days=1)
    history: list[str] = []
    raw_history = run_state.get('model_failover_apply_history', [])
    if isinstance(raw_history, list):
        for value in raw_history:
            parsed = _parse_datetime(value)
            if parsed is not None and parsed >= cutoff:
                history.append(parsed.isoformat(timespec='seconds'))
    last_applied_at = str(run_state.get('model_failover_last_applied_at', '') or '')
    parsed_last_applied = _parse_datetime(last_applied_at)
    if parsed_last_applied is not None and parsed_last_applied >= cutoff:
        normalized = parsed_last_applied.isoformat(timespec='seconds')
        if normalized not in history:
            history.append(normalized)
    history.sort()
    return history


def model_http_error_summary(engine) -> dict[str, object]:
    enabled = bool(getattr(engine.config, 'watchdog_enable_model_http_error_failover', False))
    threshold = max(1, int(getattr(engine.config, 'watchdog_model_http_error_threshold', 3) or 3))
    if not enabled:
        return {
            'enabled': False,
            'count': 0,
            'threshold': threshold,
            'threshold_reached': False,
            'latest_status': 0,
            'latest_at': '',
            'statuses': [],
            'source': 'disabled',
            'summary': 'model HTTP error failover disabled',
        }
    events, source = _recent_model_http_error_events(engine)
    statuses = [int(item.get('_status_code', 0) or 0) for item in events]
    latest = events[-1] if events else {}
    count = len(events)
    threshold_reached = count >= threshold
    latest_status = int(latest.get('_status_code', 0) or 0) if latest else 0
    latest_at = str(latest.get('_timestamp', '') or '') if latest else ''
    summary = (
        f'recent model HTTP non-200 count={count}/{threshold}'
        f' latest_status={latest_status or "none"}'
        f' source={source}'
    )
    return {
        'enabled': True,
        'count': count,
        'threshold': threshold,
        'threshold_reached': threshold_reached,
        'latest_status': latest_status,
        'latest_at': latest_at,
        'statuses': statuses,
        'source': source,
        'summary': summary,
    }


def rotate_primary_model(config_path: Path) -> dict[str, object]:
    payload = config_runtime.load_json_object(config_path, label='existing OpenClaw config', allow_jsonc=False)
    model = _model_section(payload)
    primary = str(model.get('primary', '') or '').strip()
    fallbacks = _normalized_fallbacks(model.get('fallbacks', []))
    if not primary:
        raise ValueError('OpenClaw model primary is not configured')
    next_model = ''
    remaining: list[str] = []
    for candidate in fallbacks:
        if not next_model and candidate != primary:
            next_model = candidate
            continue
        remaining.append(candidate)
    if not next_model:
        raise ValueError('OpenClaw model fallback list has no switch target')
    remaining = [candidate for candidate in remaining if candidate != next_model and candidate != primary]
    remaining.append(primary)
    model['primary'] = next_model
    model['fallbacks'] = remaining
    file_ops.write_json_atomic(config_path, payload)
    return {
        'from_model': primary,
        'to_model': next_model,
        'fallbacks': list(remaining),
    }


def apply_model_http_error_failover(engine) -> dict[str, object]:
    summary = model_http_error_summary(engine)
    run_state = _read_run_state(engine)
    now = _engine_now(engine)
    apply_history = _recent_apply_history(run_state, now)
    updates = {
        'model_http_error_count': int(summary.get('count', 0) or 0),
        'model_http_error_latest_at': str(summary.get('latest_at', '') or ''),
        'model_http_error_latest_status': int(summary.get('latest_status', 0) or 0),
        'model_failover_apply_history': list(apply_history),
        'model_failover_last_status': 'not-run',
        'model_failover_last_summary': str(summary.get('summary', '') or ''),
    }
    if not bool(summary.get('enabled', False)):
        updates['model_failover_last_status'] = 'disabled'
        _write_run_state(engine, updates)
        return {'applied': False, 'status': 'disabled', 'summary': updates['model_failover_last_summary']}
    cooldown_seconds = max(0, int(getattr(engine.config, 'watchdog_model_http_error_cooldown_seconds', 1800) or 1800))
    remaining = _cooldown_remaining_seconds(
        now,
        str(run_state.get('model_failover_last_applied_at', '') or ''),
        cooldown_seconds,
    )
    if remaining > 0:
        updates['model_failover_last_status'] = 'cooldown'
        updates['model_failover_last_summary'] = f'model failover cooldown active ({remaining}s remaining)'
        _write_run_state(engine, updates)
        return {'applied': False, 'status': 'cooldown', 'summary': updates['model_failover_last_summary']}
    if not bool(summary.get('threshold_reached', False)):
        updates['model_failover_last_status'] = 'insufficient-evidence'
        _write_run_state(engine, updates)
        return {'applied': False, 'status': 'insufficient-evidence', 'summary': updates['model_failover_last_summary']}
    max_applies_per_day = max(0, int(getattr(engine.config, 'watchdog_model_failover_max_applies_per_day', 3) or 0))
    if max_applies_per_day > 0 and len(apply_history) >= max_applies_per_day:
        updates['model_failover_last_status'] = 'rate-limited'
        updates['model_failover_last_summary'] = (
            f'model failover daily rate limit reached ({len(apply_history)}/{max_applies_per_day} applies in last 24h)'
        )
        _write_run_state(engine, updates)
        return {'applied': False, 'status': 'rate-limited', 'summary': updates['model_failover_last_summary']}
    try:
        rotation = rotate_primary_model(engine.config.openclaw_config)
    except ValueError as exc:
        updates['model_failover_last_status'] = 'not-configured'
        updates['model_failover_last_summary'] = str(exc)
        _write_run_state(engine, updates)
        return {'applied': False, 'status': 'not-configured', 'summary': str(exc)}
    except Exception as exc:
        updates['model_failover_last_status'] = 'failed'
        updates['model_failover_last_summary'] = f'model failover update failed: {exc}'
        _write_run_state(engine, updates)
        return {'applied': False, 'status': 'failed', 'summary': updates['model_failover_last_summary']}

    updates.update(
        {
            'model_failover_last_applied_at': now.isoformat(timespec='seconds'),
            'model_failover_apply_history': list(apply_history) + [now.isoformat(timespec='seconds')],
            'model_failover_last_from_model': str(rotation.get('from_model', '') or ''),
            'model_failover_last_to_model': str(rotation.get('to_model', '') or ''),
            'model_failover_last_status': 'applied',
            'model_failover_last_summary': (
                f"switched primary model {rotation.get('from_model', '')} -> {rotation.get('to_model', '')}"
            ).strip(),
        }
    )
    _write_run_state(engine, updates)
    _log(
        engine,
        'WARN',
        (
            'model HTTP non-200 threshold reached; '
            f"switching primary model {rotation.get('from_model', '')} -> {rotation.get('to_model', '')}"
        ),
    )
    return {
        'applied': True,
        'status': 'applied',
        'summary': updates['model_failover_last_summary'],
        'from_model': updates['model_failover_last_from_model'],
        'to_model': updates['model_failover_last_to_model'],
    }
