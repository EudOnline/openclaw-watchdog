from __future__ import annotations

from openclaw_watchdog import health_probe_runtime
from openclaw_watchdog import health_status_runtime


def service_level_probe(engine) -> dict[str, object]:
    return health_probe_runtime.service_level_probe(engine)


def conversation_level_probe(engine, status_payload: dict[str, object] | None, *, service_layer_healthy: bool) -> dict[str, object]:
    return health_probe_runtime.conversation_level_probe(
        engine,
        status_payload,
        service_layer_healthy=service_layer_healthy,
    )


def raw_live_probe(engine) -> dict[str, object]:
    return health_probe_runtime.raw_live_probe(engine)


def live_probe(engine, *, include_doctor: bool, apply_grace: bool = True) -> dict[str, object]:
    return health_probe_runtime.live_probe(engine, include_doctor=include_doctor, apply_grace=apply_grace)


def healthy_now(engine) -> bool:
    return health_probe_runtime.healthy_now(engine)


def read_last_event(engine) -> dict[str, object]:
    return health_status_runtime.read_last_event(engine)


def maintenance_status_payload(engine) -> dict[str, object]:
    return health_status_runtime.maintenance_status_payload(engine)


def status_payload(engine) -> dict[str, object]:
    return health_status_runtime.status_payload(engine)
