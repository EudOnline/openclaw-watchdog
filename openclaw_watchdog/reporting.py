from __future__ import annotations

from openclaw_watchdog import metrics_runtime
from openclaw_watchdog import report_payload_runtime


def report_attention_items(report: dict[str, object]) -> list[str]:
    return report_payload_runtime.report_attention_items(report)


def message_report_text(report: dict[str, object]) -> str:
    return report_payload_runtime.message_report_text(report)


def prometheus_metrics_text(metrics: dict[str, object]) -> str:
    return metrics_runtime.prometheus_metrics_text(metrics)


def metrics_payload(engine) -> dict[str, object]:
    return metrics_runtime.metrics_payload(engine)


def report_payload(engine, *, incident_limit: int = 5) -> dict[str, object]:
    return report_payload_runtime.report_payload(engine, incident_limit=incident_limit)
