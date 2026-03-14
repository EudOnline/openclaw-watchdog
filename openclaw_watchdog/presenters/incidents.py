from __future__ import annotations


def render_incident_queue(payload: dict[str, object]) -> str:
    summary = payload.get('summary', {}) if isinstance(payload.get('summary', {}), dict) else {}
    incidents = payload.get('incidents', [])
    lines = [
        f"open_total={summary.get('open_total', 0)}",
        f"attention_total={summary.get('attention_total', 0)}",
        f"handled_total={summary.get('handled_total', 0)}",
        f"owned_total={summary.get('owned_total', 0)}",
        f"acknowledged_total={summary.get('acknowledged_total', 0)}",
        f"with_notes_total={summary.get('with_notes_total', 0)}",
        f"queue_count={len(incidents) if isinstance(incidents, list) else 0}",
    ]
    if isinstance(incidents, list):
        for idx, incident in enumerate(incidents, start=1):
            if not isinstance(incident, dict):
                continue
            latest_note = incident.get('latest_note', '') or ''
            latest_note_suffix = f' | note={latest_note}' if latest_note else ''
            lines.append(
                f"queue_{idx}={incident.get('incident_id', 'none')} | {incident.get('state', 'unknown')} | {incident.get('health_level', 'unknown')} | "
                f"owner={incident.get('owner', '') or 'none'} | ack={str(bool(incident.get('acknowledged', False))).lower()} | notes={incident.get('notes_count', 0)} | "
                f"attention={incident.get('attention_summary', 'none') or 'none'} | {incident.get('summary', '')}{latest_note_suffix}"
            )
    return '\n'.join(lines)
