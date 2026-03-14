from __future__ import annotations


def run(*, args, config, bootstrapper_type, json_printer, bootstrap_printer) -> int:
    outcome = bootstrapper_type(config).run()
    if getattr(args, 'json', False):
        json_printer(outcome.payload)
    else:
        bootstrap_printer(outcome)
    return int(outcome.exit_code)
