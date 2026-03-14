from __future__ import annotations

import argparse
from pathlib import Path

from openclaw_watchdog.bootstrap import Bootstrapper
from openclaw_watchdog import cli_output
from openclaw_watchdog.cli_commands import (
    bootstrap_command,
    incidents_command,
    maintenance_command,
    metrics_command,
    report_command,
    run_once_command,
    status_command,
)
from openclaw_watchdog.config import Config, default_env_file
from openclaw_watchdog.detect import detect_payload, print_detect, write_suggested_env
from openclaw_watchdog.engine import WatchdogEngine
from openclaw_watchdog import health as health_ops
from openclaw_watchdog import incidents as incident_ops
from openclaw_watchdog import maintenance_runtime
from openclaw_watchdog import reporting as reporting_ops


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="openclaw-watchdog",
        description="External watchdog and recovery toolkit for OpenClaw.",
        epilog=(
            "Operator quick path: detect -> check -> status --summary -> "
            "report --message -> incidents queue -> maintenance on|off"
        ),
    )
    parser.add_argument("--env", type=Path, default=default_env_file())
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_once = subparsers.add_parser("run-once", help="Run one watchdog remediation pass")
    run_once.add_argument("--json", action="store_true")

    check = subparsers.add_parser("check", help="Check health without remediating")
    check.add_argument("--json", action="store_true")

    detect = subparsers.add_parser("detect", help="Inspect the current host and suggest a safer first-deployment config")
    detect.add_argument("--json", action="store_true")
    detect.add_argument("--write-suggested-config", type=Path, default=None, help="Write a suggested env file without enabling any live repair behavior")

    status = subparsers.add_parser("status", help="Show current watchdog state")
    status.add_argument("--json", action="store_true")
    status.add_argument("--summary", action="store_true", help="Print a compact one-line summary")

    report = subparsers.add_parser("report", help="Show compact watchdog report for humans or machines")
    report.add_argument("--json", action="store_true")
    report.add_argument("--message", action="store_true", help="Print message-ready multiline text")
    report.add_argument("--limit", type=int, default=5, help="How many recent incidents to include")

    metrics = subparsers.add_parser("metrics", help="Show normalized watchdog metrics for scripts or dashboards")
    metrics.add_argument("--json", action="store_true")
    metrics.add_argument("--prometheus", action="store_true", help="Print Prometheus text exposition format")

    incidents = subparsers.add_parser("incidents", help="List or inspect watchdog incident bundles")
    incidents_sub = incidents.add_subparsers(dest="incidents_command", required=True)
    incidents_list = incidents_sub.add_parser("list", help="List recent incidents")
    incidents_list.add_argument("--json", action="store_true")
    incidents_list.add_argument("--limit", type=int, default=10, help="How many incidents to show")
    incidents_list.add_argument("--state", choices=["all", "open", "resolved"], default="all")
    incidents_list.add_argument("--owner", default="", help="Filter incidents by exact owner")
    incidents_list.add_argument("--ack", choices=["all", "yes", "no"], default="all", help="Filter incidents by acknowledgement state")
    incidents_list.add_argument("--notes", choices=["all", "yes", "no"], default="all", help="Filter incidents by whether operator notes exist")
    incidents_list.add_argument("--attention", choices=["all", "yes", "no"], default="all", help="Filter incidents by whether operator attention is still needed")
    incidents_show = incidents_sub.add_parser("show", help="Show one incident in detail")
    incidents_show.add_argument("incident_id")
    incidents_show.add_argument("--json", action="store_true")
    incidents_show.add_argument("--notes-all", action="store_true", help="Print all notes in text mode instead of only recent notes")
    incidents_current = incidents_sub.add_parser("current", help="Show the current active incident if there is one")
    incidents_current.add_argument("--json", action="store_true")
    incidents_queue = incidents_sub.add_parser("queue", help="Show the open-incident operator queue")
    incidents_queue.add_argument("--json", action="store_true")
    incidents_queue.add_argument("--limit", type=int, default=10, help="How many open incidents to show")
    incidents_timeline = incidents_sub.add_parser("timeline", help="Show incident timeline events")
    incidents_timeline.add_argument("incident_id")
    incidents_timeline.add_argument("--json", action="store_true")
    incidents_timeline.add_argument("--limit", type=int, default=0, help="Only show the latest N timeline events")
    incidents_assign = incidents_sub.add_parser("assign", help="Assign an owner to an incident")
    incidents_assign.add_argument("incident_id")
    incidents_assign.add_argument("--owner", required=True)
    incidents_assign.add_argument("--json", action="store_true")
    incidents_unassign = incidents_sub.add_parser("unassign", help="Clear the owner from an incident")
    incidents_unassign.add_argument("incident_id")
    incidents_unassign.add_argument("--json", action="store_true")
    incidents_ack = incidents_sub.add_parser("ack", help="Acknowledge an incident")
    incidents_ack.add_argument("incident_id")
    incidents_ack.add_argument("--by", required=True)
    incidents_ack.add_argument("--note", default="")
    incidents_ack.add_argument("--json", action="store_true")
    incidents_unack = incidents_sub.add_parser("unack", help="Clear incident acknowledgement")
    incidents_unack.add_argument("incident_id")
    incidents_unack.add_argument("--json", action="store_true")
    incidents_note = incidents_sub.add_parser("note", help="Add an operator note to an incident")
    incidents_note.add_argument("incident_id")
    incidents_note.add_argument("--by", required=True)
    incidents_note.add_argument("--message", required=True)
    incidents_note.add_argument("--json", action="store_true")

    bootstrap = subparsers.add_parser(
        "bootstrap",
        help="Inspect rescue-chain availability and OpenClaw prerequisite readiness",
    )
    bootstrap.add_argument("--json", action="store_true")

    maintenance = subparsers.add_parser("maintenance", help="Manage maintenance mode")
    maintenance_sub = maintenance.add_subparsers(dest="maintenance_command", required=True)
    maintenance_on = maintenance_sub.add_parser("on", help="Enable maintenance mode")
    maintenance_on.add_argument("--reason", default="")
    maintenance_on.add_argument("--json", action="store_true")
    maintenance_off = maintenance_sub.add_parser("off", help="Disable maintenance mode")
    maintenance_off.add_argument("--json", action="store_true")
    maintenance_status = maintenance_sub.add_parser("status", help="Show maintenance status")
    maintenance_status.add_argument("--json", action="store_true")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    env_file = args.env if args.env and args.env.exists() else args.env
    config = Config.load(env_file)

    if args.command == "bootstrap":
        return bootstrap_command.run(
            args=args,
            config=config,
            bootstrapper_type=Bootstrapper,
            json_printer=cli_output.print_json,
            bootstrap_printer=cli_output.print_bootstrap,
        )

    with WatchdogEngine(config) as engine:
        if args.command in {"run-once", "check", "detect"}:
            return run_once_command.run(
                args=args,
                engine=engine,
                config=config,
                health_ops=health_ops,
                detect_payload_fn=detect_payload,
                detect_printer=print_detect,
                write_suggested_env_fn=write_suggested_env,
                json_printer=cli_output.print_json,
                run_once_printer=cli_output.print_run_once,
                check_printer=cli_output.print_check,
            )

        if args.command == "status":
            return status_command.run(
                args=args,
                engine=engine,
                health_ops=health_ops,
                json_printer=cli_output.print_json,
                summary_printer=cli_output.print_status_summary,
                status_printer=cli_output.print_status,
            )

        if args.command == "report":
            return report_command.run(
                args=args,
                engine=engine,
                reporting_ops=reporting_ops,
                json_printer=cli_output.print_json,
                report_printer=cli_output.print_report,
            )

        if args.command == "metrics":
            return metrics_command.run(
                args=args,
                engine=engine,
                reporting_ops=reporting_ops,
                json_printer=cli_output.print_json,
                metrics_printer=cli_output.print_metrics,
            )

        if args.command == "incidents":
            return incidents_command.run(
                args=args,
                engine=engine,
                incident_ops=incident_ops,
                json_printer=cli_output.print_json,
                incidents_list_printer=cli_output.print_incidents_list,
                incident_detail_printer=cli_output.print_incident_detail,
                incident_queue_printer=cli_output.print_incident_queue,
                incident_timeline_printer=cli_output.print_incident_timeline,
            )

        if args.command == "maintenance":
            return maintenance_command.run(
                args=args,
                engine=engine,
                health_ops=health_ops,
                maintenance_runtime=maintenance_runtime,
                json_printer=cli_output.print_json,
                maintenance_printer=cli_output.print_maintenance,
            )

    return 2
