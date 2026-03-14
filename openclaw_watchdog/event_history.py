from __future__ import annotations

from datetime import datetime, timedelta

from openclaw_watchdog import state_store


def append_event_history(engine, event_payload: dict[str, object]) -> None:
    state_store.append_event_history(
        engine.config.watchdog_event_history_file,
        event_payload,
        keep=engine.config.watchdog_event_history_limit,
    )


def read_event_history(engine, limit: int | None = None) -> list[dict[str, object]]:
    return state_store.read_event_history(engine.config.watchdog_event_history_file, limit=limit)


def event_time(event: dict[str, object]) -> datetime | None:
    raw = event.get("time")
    if not isinstance(raw, str) or not raw:
        return None
    local_tz = datetime.now().astimezone().tzinfo
    for fmt in ("%Y-%m-%d %H:%M:%S %Z", "%Y-%m-%d %H:%M:%S"):
        try:
            dt = datetime.strptime(raw, fmt)
            return dt.astimezone() if dt.tzinfo else dt.replace(tzinfo=local_tz)
        except ValueError:
            continue
    if len(raw) >= 19:
        try:
            return datetime.strptime(raw[:19], "%Y-%m-%d %H:%M:%S").replace(tzinfo=local_tz)
        except ValueError:
            pass
    try:
        dt = datetime.fromisoformat(raw)
        return dt if dt.tzinfo else dt.replace(tzinfo=local_tz)
    except ValueError:
        return None


def recent_event_stats(engine, *, hours: int = 24) -> dict[str, object]:
    now = datetime.now().astimezone()
    cutoff = now - timedelta(hours=max(1, hours))
    events = read_event_history(engine)
    window: list[dict[str, object]] = []
    for event in events:
        when = event_time(event)
        if when is None or when >= cutoff:
            window.append(event)
    counts = {
        "ok": 0,
        "info": 0,
        "warning": 0,
        "success": 0,
        "critical": 0,
        "healthy": 0,
        "degraded": 0,
        "recovered": 0,
        "failed": 0,
    }
    last_recovered_at = ""
    healthy_streak_start = ""
    last_nonhealthy_at = ""
    current_streak = 0
    max_streak = 0
    current_streak_duration_seconds = 0
    longest_healthy_gap_seconds = 0
    recovery_durations_seconds: list[int] = []
    failed_started_at: datetime | None = None
    previous_healthy_time: datetime | None = None
    for event in window:
        severity = str(event.get("severity", "info"))
        status = str(event.get("status", "unknown"))
        counts[severity] = counts.get(severity, 0) + 1
        counts[status] = counts.get(status, 0) + 1
        when = event_time(event)
        when_text = str(event.get("time", ""))
        if status == "failed" and when is not None and failed_started_at is None:
            failed_started_at = when
        elif status == "recovered" and when is not None:
            last_recovered_at = when_text
            if failed_started_at is not None:
                recovery_durations_seconds.append(max(0, int((when - failed_started_at).total_seconds())))
                failed_started_at = None
        if status == "healthy":
            if previous_healthy_time is not None and when is not None:
                longest_healthy_gap_seconds = max(longest_healthy_gap_seconds, max(0, int((when - previous_healthy_time).total_seconds())))
            previous_healthy_time = when
            current_streak += 1
            if current_streak == 1:
                healthy_streak_start = when_text
            if when is not None:
                streak_start_dt = event_time({"time": healthy_streak_start}) if healthy_streak_start else None
                if streak_start_dt is not None:
                    current_streak_duration_seconds = max(0, int((when - streak_start_dt).total_seconds()))
        else:
            current_streak = 0
            current_streak_duration_seconds = 0
            previous_healthy_time = None
            if when_text:
                last_nonhealthy_at = when_text
                healthy_streak_start = ""
        max_streak = max(max_streak, current_streak)
    last_recovery_duration_seconds = recovery_durations_seconds[-1] if recovery_durations_seconds else 0
    return {
        "window_hours": max(1, hours),
        "total": len(window),
        "counts": counts,
        "last_recovered_at": last_recovered_at,
        "last_nonhealthy_at": last_nonhealthy_at,
        "healthy_streak_events": current_streak,
        "healthy_streak_start": healthy_streak_start,
        "healthy_streak_best": max_streak,
        "healthy_streak_duration_seconds": current_streak_duration_seconds,
        "longest_healthy_gap_seconds": longest_healthy_gap_seconds,
        "last_recovery_duration_seconds": last_recovery_duration_seconds,
    }
