from __future__ import annotations


def run(*, args, engine, health_ops, json_printer, summary_printer, status_printer) -> int:
    payload = health_ops.status_payload(engine)
    if getattr(args, 'json', False):
        json_printer(payload)
    elif getattr(args, 'summary', False):
        summary_printer(payload)
    else:
        status_printer(payload)
    return 0
