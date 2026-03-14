from __future__ import annotations


def run(
    *,
    args,
    engine,
    config,
    health_ops,
    detect_payload_fn,
    detect_printer,
    write_suggested_env_fn,
    json_printer,
    run_once_printer,
    check_printer,
) -> int:
    command = str(getattr(args, 'command', '') or '')
    if command == 'run-once':
        if not engine.acquire_lock():
            payload = {'state': 'locked', 'summary': f'lock busy: {config.watchdog_lock_file}'}
            if getattr(args, 'json', False):
                json_printer(payload)
            else:
                print(f"state={payload['state']}")
                print(f"summary={payload['summary']}")
            return 0
        outcome = engine.run_once()
        if getattr(args, 'json', False):
            json_printer({'state': outcome.state, 'summary': outcome.summary, 'exit_code': outcome.exit_code})
        else:
            run_once_printer(outcome)
        return int(outcome.exit_code)

    if command == 'check':
        payload = health_ops.live_probe(engine, include_doctor=True)
        if getattr(args, 'json', False):
            json_printer(payload)
        else:
            check_printer(payload)
        return 0 if payload['healthy'] else 1

    if command == 'detect':
        payload = detect_payload_fn(engine)
        if getattr(args, 'write_suggested_config', None):
            written = write_suggested_env_fn(payload, args.write_suggested_config)
            payload['suggested_config_written'] = str(written)
        if getattr(args, 'json', False):
            json_printer(payload)
        else:
            detect_printer(payload)
            if payload.get('suggested_config_written'):
                print(f"suggested_config_written={payload['suggested_config_written']}")
        return 0

    raise ValueError(f'unsupported run command: {command}')
