from __future__ import annotations


def run(*, args, engine, reporting_ops, json_printer, metrics_printer) -> int:
    payload = reporting_ops.metrics_payload(engine)
    if getattr(args, 'json', False):
        json_printer(payload)
    elif getattr(args, 'prometheus', False):
        print(reporting_ops.prometheus_metrics_text(payload), end='')
    else:
        metrics_printer(payload)
    return 0
