from __future__ import annotations


def run(*, args, engine, health_ops, maintenance_runtime, json_printer, maintenance_printer) -> int:
    if args.maintenance_command == 'on':
        payload = maintenance_runtime.maintenance_on(engine, reason=args.reason)
    elif args.maintenance_command == 'off':
        payload = maintenance_runtime.maintenance_off(engine)
    else:
        payload = health_ops.maintenance_status_payload(engine)
    if getattr(args, 'json', False):
        json_printer(payload)
    else:
        maintenance_printer(payload)
    return 0
