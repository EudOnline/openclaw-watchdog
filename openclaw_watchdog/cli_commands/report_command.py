from __future__ import annotations


def run(*, args, engine, reporting_ops, json_printer, report_printer) -> int:
    payload = reporting_ops.report_payload(engine, incident_limit=max(1, getattr(args, 'limit', 5)))
    if getattr(args, 'json', False):
        json_printer(payload)
    elif getattr(args, 'message', False):
        print(payload.get('message_text', ''))
    else:
        report_printer(payload)
    return 0
