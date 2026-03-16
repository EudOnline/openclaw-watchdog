from __future__ import annotations

import re
import time
import uuid
from datetime import datetime

from openclaw_watchdog import state_store

PROBE_PREFIX = 'openclaw-watchdog-probe:'
_NONCE_PATTERN = re.compile(r'openclaw-watchdog-probe:([A-Za-z0-9-]+)')


def generate_probe_nonce() -> str:
    return uuid.uuid4().hex[:12]


def _probe_message(nonce: str) -> str:
    return f'{PROBE_PREFIX}{nonce}'


def _coerce_bool(value: object) -> bool | None:
    if isinstance(value, bool):
        return value
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return bool(value)
    text = str(value).strip().lower()
    if text in {'1', 'true', 'yes', 'on', 'ok', 'success'}:
        return True
    if text in {'0', 'false', 'no', 'off', 'failed', 'error'}:
        return False
    return None


def _timestamp_to_datetime(value: object) -> datetime | None:
    if isinstance(value, (int, float)):
        raw = float(value)
        if raw > 1_000_000_000_000:
            raw /= 1000.0
        return datetime.fromtimestamp(raw).astimezone()
    text = str(value or '').strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def _event_timestamp(record: dict[str, object]) -> datetime | None:
    context = record.get('context') if isinstance(record.get('context'), dict) else {}
    for candidate in (record.get('timestamp'), context.get('timestamp')):
        parsed = _timestamp_to_datetime(candidate)
        if parsed is not None:
            return parsed
    return None


def _normalize_event(record: dict[str, object]) -> dict[str, object] | None:
    if not isinstance(record, dict):
        return None
    context = record.get('context') if isinstance(record.get('context'), dict) else {}
    action = str(record.get('action', context.get('action', '')) or '').strip().lower()
    if action not in {'sent', 'received'}:
        return None
    return {
        'action': action,
        'timestamp': _event_timestamp(record),
        'channel': str(context.get('channelId', record.get('channel', '')) or '').strip(),
        'account': str(context.get('accountId', record.get('account', '')) or '').strip(),
        'to': str(context.get('to', record.get('to', '')) or '').strip(),
        'from': str(context.get('from', record.get('from', '')) or '').strip(),
        'content': str(context.get('content', record.get('content', '')) or ''),
        'success': _coerce_bool(context.get('success', record.get('success'))),
    }


def _read_events(path) -> list[dict[str, object]]:
    return [record for record in state_store.read_event_history(path, limit=400) if isinstance(record, dict)]


def _event_nonce(event: dict[str, object]) -> str:
    match = _NONCE_PATTERN.search(str(event.get('content', '') or ''))
    return match.group(1) if match else ''


def _same_channel_and_account(engine, event: dict[str, object]) -> bool:
    channel = str(getattr(engine.config, 'watchdog_message_loop_probe_channel', '') or '').strip()
    account = str(getattr(engine.config, 'watchdog_message_loop_probe_account', '') or '').strip()
    if channel and str(event.get('channel', '') or '').strip() != channel:
        return False
    if account and str(event.get('account', '') or '').strip() != account:
        return False
    return True


def _sent_match(engine, event: dict[str, object], *, nonce: str) -> bool:
    if str(event.get('action', '')) != 'sent':
        return False
    if not _same_channel_and_account(engine, event):
        return False
    target = str(getattr(engine.config, 'watchdog_message_loop_probe_target', '') or '').strip()
    if target and str(event.get('to', '') or '').strip() != target:
        return False
    success = event.get('success')
    if success is False:
        return False
    return _event_nonce(event) == nonce


def _received_match(engine, event: dict[str, object], *, nonce: str) -> bool:
    if str(event.get('action', '')) != 'received':
        return False
    if not _same_channel_and_account(engine, event):
        return False
    reply_from = str(getattr(engine.config, 'watchdog_message_loop_probe_reply_from', '') or '').strip()
    if reply_from and str(event.get('from', '') or '').strip() != reply_from:
        return False
    return _event_nonce(event) == nonce


def _probe_state_for_nonce(engine, records: list[dict[str, object]], *, nonce: str) -> tuple[bool, bool]:
    sent = False
    received = False
    for raw in records:
        event = _normalize_event(raw)
        if event is None:
            continue
        if _sent_match(engine, event, nonce=nonce):
            sent = True
        if _received_match(engine, event, nonce=nonce):
            received = True
        if sent and received:
            return True, True
    return sent, received


def _cached_probe_result(engine, records: list[dict[str, object]], *, checked_at: str) -> dict[str, object] | None:
    cooldown_seconds = int(getattr(engine.config, 'watchdog_message_loop_probe_cooldown_seconds', 0) or 0)
    if cooldown_seconds <= 0:
        return None
    checked_time = _timestamp_to_datetime(checked_at)
    if checked_time is None:
        return None

    latest_probe_nonce = ''
    latest_probe_at: datetime | None = None
    for raw in records:
        event = _normalize_event(raw)
        if event is None:
            continue
        nonce = _event_nonce(event)
        event_time = event.get('timestamp')
        if not nonce or not isinstance(event_time, datetime):
            continue
        if str(event.get('action', '')) != 'sent':
            continue
        if not _sent_match(engine, event, nonce=nonce):
            continue
        if latest_probe_at is None or event_time > latest_probe_at:
            latest_probe_at = event_time
            latest_probe_nonce = nonce
    if latest_probe_at is None or not latest_probe_nonce:
        return None
    age_seconds = (checked_time - latest_probe_at).total_seconds()
    if age_seconds < 0 or age_seconds > cooldown_seconds:
        return None
    sent, received = _probe_state_for_nonce(engine, records, nonce=latest_probe_nonce)
    ready = sent and received
    summary = 'message loop cached ready' if ready else 'message loop cached waiting echo'
    return {
        'message_loop_probe_enabled': True,
        'message_loop_probe_attempted': False,
        'message_loop_probe_ready': ready,
        'message_loop_probe_sent': sent,
        'message_loop_probe_echo_received': received,
        'message_loop_probe_summary': summary,
        'message_loop_probe_cached': True,
        'message_loop_probe_nonce': latest_probe_nonce,
        'message_loop_probe_checked_at': checked_at,
        'message_loop_probe_events_file': str(engine.config.watchdog_message_loop_probe_events_file),
    }


def message_loop_probe(engine, *, monotonic_fn=time.monotonic, sleep_fn=time.sleep) -> dict[str, object]:
    checked_at = engine.now_iso()
    events_file = engine.config.watchdog_message_loop_probe_events_file
    if not bool(getattr(engine.config, 'watchdog_enable_message_loop_probe', False)):
        return {
            'message_loop_probe_enabled': False,
            'message_loop_probe_attempted': False,
            'message_loop_probe_ready': False,
            'message_loop_probe_sent': False,
            'message_loop_probe_echo_received': False,
            'message_loop_probe_summary': 'disabled',
            'message_loop_probe_cached': False,
            'message_loop_probe_nonce': '',
            'message_loop_probe_checked_at': checked_at,
            'message_loop_probe_events_file': str(events_file),
        }

    records = _read_events(events_file)
    cached = _cached_probe_result(engine, records, checked_at=checked_at)
    if cached is not None:
        return cached

    channel = str(getattr(engine.config, 'watchdog_message_loop_probe_channel', '') or '').strip()
    target = str(getattr(engine.config, 'watchdog_message_loop_probe_target', '') or '').strip()
    if not channel or not target:
        return {
            'message_loop_probe_enabled': True,
            'message_loop_probe_attempted': False,
            'message_loop_probe_ready': False,
            'message_loop_probe_sent': False,
            'message_loop_probe_echo_received': False,
            'message_loop_probe_summary': 'misconfigured: set WATCHDOG_MESSAGE_LOOP_PROBE_CHANNEL and WATCHDOG_MESSAGE_LOOP_PROBE_TARGET',
            'message_loop_probe_cached': False,
            'message_loop_probe_nonce': '',
            'message_loop_probe_checked_at': checked_at,
            'message_loop_probe_events_file': str(events_file),
        }

    nonce = generate_probe_nonce()
    result = engine.run_command(
        [
            'openclaw',
            'message',
            'send',
            '--account',
            engine.config.watchdog_message_loop_probe_account,
            '--channel',
            channel,
            '--target',
            target,
            '--message',
            _probe_message(nonce),
        ],
        timeout=min(
            int(getattr(engine.config, 'watchdog_message_timeout_seconds', 20) or 20),
            int(getattr(engine.config, 'watchdog_message_loop_probe_timeout_seconds', 20) or 20),
        ),
    )
    if result.returncode != 0:
        return {
            'message_loop_probe_enabled': True,
            'message_loop_probe_attempted': True,
            'message_loop_probe_ready': False,
            'message_loop_probe_sent': False,
            'message_loop_probe_echo_received': False,
            'message_loop_probe_summary': f'message loop send failed rc={result.returncode}: {(result.output or "").strip()}',
            'message_loop_probe_cached': False,
            'message_loop_probe_nonce': nonce,
            'message_loop_probe_checked_at': checked_at,
            'message_loop_probe_events_file': str(events_file),
        }

    sent = False
    received = False
    deadline = monotonic_fn() + int(getattr(engine.config, 'watchdog_message_loop_probe_timeout_seconds', 20) or 20)
    while True:
        records = _read_events(events_file)
        sent, received = _probe_state_for_nonce(engine, records, nonce=nonce)
        if sent and received:
            return {
                'message_loop_probe_enabled': True,
                'message_loop_probe_attempted': True,
                'message_loop_probe_ready': True,
                'message_loop_probe_sent': True,
                'message_loop_probe_echo_received': True,
                'message_loop_probe_summary': 'message loop ready',
                'message_loop_probe_cached': False,
                'message_loop_probe_nonce': nonce,
                'message_loop_probe_checked_at': checked_at,
                'message_loop_probe_events_file': str(events_file),
            }
        if monotonic_fn() >= deadline:
            break
        sleep_fn(0.2)

    if sent:
        summary = 'message loop timeout waiting echo'
    else:
        summary = 'message loop timeout waiting hook events'
    return {
        'message_loop_probe_enabled': True,
        'message_loop_probe_attempted': True,
        'message_loop_probe_ready': False,
        'message_loop_probe_sent': sent,
        'message_loop_probe_echo_received': received,
        'message_loop_probe_summary': summary,
        'message_loop_probe_cached': False,
        'message_loop_probe_nonce': nonce,
        'message_loop_probe_checked_at': checked_at,
        'message_loop_probe_events_file': str(events_file),
    }
