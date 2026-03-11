from __future__ import annotations

import json
import os
import re
import shlex
import shutil
import textwrap
import time
from datetime import datetime
from pathlib import Path


def prune_incident_archives(engine) -> None:
    all_dirs = sorted((path for path in engine.config.watchdog_incidents_dir.iterdir() if path.is_dir()), reverse=True)
    for path in all_dirs[engine.config.watchdog_keep_incidents :]:
        shutil.rmtree(path, ignore_errors=True)
        engine.log("INFO", f"pruned incident archive id={path.name}")


def ensure_incident_context(engine) -> None:
    incident_id = ""
    if engine.current_incident_marker.exists():
        incident_id = engine.current_incident_marker.read_text(encoding="utf-8").strip()
        if incident_id and not (engine.config.watchdog_incidents_dir / incident_id).is_dir():
            incident_id = ""
            engine.current_incident_marker.unlink(missing_ok=True)
    if not incident_id:
        incident_id = datetime.now().strftime("%Y%m%d-%H%M%S")
        (engine.config.watchdog_incidents_dir / incident_id).mkdir(parents=True, exist_ok=True)
        engine.current_incident_marker.write_text(f"{incident_id}\n", encoding="utf-8")
        prune_incident_archives(engine)
    ctx = engine.ctx
    ctx.incident_id = incident_id
    ctx.incident_dir = engine.config.watchdog_incidents_dir / incident_id
    ctx.codex_prompt_file = ctx.incident_dir / "codex-prompt.md"
    ctx.codex_handoff_file = ctx.incident_dir / "run-codex.sh"
    ctx.codex_runner_file = ctx.incident_dir / "codex-runner.sh"
    ctx.codex_run_log_file = ctx.incident_dir / "codex-run.log"
    ctx.codex_autorun_ready = True
    ctx.opencode_fallback_handoff_file = ctx.incident_dir / "run-opencode-fallback.sh"
    ctx.opencode_fallback_runner_file = ctx.incident_dir / "opencode-fallback-runner.sh"
    ctx.opencode_fallback_run_log_file = ctx.incident_dir / "opencode-fallback.log"
    engine.update_incident_state("open", "incident created")


def copy_if_exists(engine, src: Path, dest: Path) -> None:
    if src.exists() and src.is_file():
        shutil.copy2(src, dest)


def render_codex_prompt(engine, summary: str) -> None:
    if engine.incident_dir is None or engine.codex_prompt_file is None:
        return
    prompt = textwrap.dedent(
        f"""\
        # OpenClaw rescue handoff prompt

        ## Goal
        Repair the local OpenClaw installation so that:
        1. systemctl --user is-active {engine.config.openclaw_gateway_service} returns active
        2. openclaw doctor --non-interactive does not report Config invalid
        3. Port {engine.config.openclaw_gateway_port} is listened by the systemd MainPID or one of its child processes
        4. Two consecutive watchdog runs would consider the system healthy

        ## Incident context
        - Incident ID: {engine.incident_id}
        - Incident directory: {engine.incident_dir}
        - Time: {engine.run_ts}
        - Summary: {summary}
        - Pre-repair backup result: {engine.pre_repair_backup_result}
        - Rollback occurred: {'true' if engine.rollback_occurred else 'false'}
        - Suggested model hint: {engine.config.watchdog_codex_model_hint}

        ## Evidence files
        - doctor.out
        - openclaw-status.json
        - gateway-status.txt
        - systemctl-status.txt
        - journal-tail.txt
        - listeners.txt
        - watchdog-log-tail.txt
        - current-openclaw.json
        - last-good-openclaw.json
        - last-rollback-summary.txt
        - incident-meta.txt

        ## Allowed edits
        - {engine.config.openclaw_config}
        - ~/.config/systemd/user/{engine.config.openclaw_gateway_service}
        - {engine.config.repo_root}/scripts/openclaw-watchdog
        - {engine.config.repo_root}/watchdog_v2/*
        - {engine.config.repo_root}/config/*.env

        ## Forbidden actions
        - Do not reboot the machine
        - Do not delete /root/.openclaw
        - Do not modify unrelated services
        - Do not upgrade the entire OS or install random packages without need
        - Do not disable backups or watchdog safety rails

        ## Validation commands
        - systemctl --user is-active {engine.config.openclaw_gateway_service}
        - systemctl --user show -p MainPID --value {engine.config.openclaw_gateway_service}
        - ss -tlnp | grep :{engine.config.openclaw_gateway_port}
        - openclaw doctor --non-interactive
        - openclaw gateway status

        ## Expected workflow
        1. Read the evidence files in this incident directory
        2. Identify the most likely root cause
        3. Apply the smallest safe fix
        4. Re-run the validation commands
        5. Write a concise repair summary to repair-result.txt in this incident directory
        6. Document exactly what changed and why
        """
    )
    engine.codex_prompt_file.write_text(prompt, encoding="utf-8")

    codex_runner = textwrap.dedent(
        f"""\
        #!/usr/bin/env bash
        set -euo pipefail
        cd {shlex.quote(str(engine.config.watchdog_codex_workdir))}
        if [[ {shlex.quote(engine.config.watchdog_codex_bin)} == */* ]]; then
          [[ -x {shlex.quote(engine.config.watchdog_codex_bin)} ]] || {{ echo {shlex.quote(engine.config.watchdog_codex_bin)}' CLI not found'; exit 127; }}
        else
          command -v {shlex.quote(engine.config.watchdog_codex_bin)} >/dev/null 2>&1 || {{ echo {shlex.quote(engine.config.watchdog_codex_bin)}' CLI not found in PATH'; exit 127; }}
        fi
        PROMPT_FILE={shlex.quote(str(engine.codex_prompt_file))}
        LOG_FILE={shlex.quote(str(engine.codex_run_log_file))}
        LAST_MESSAGE_FILE={shlex.quote(str(engine.incident_dir / 'codex-last-message.txt'))}
        CMD=({shlex.quote(engine.config.watchdog_codex_bin)} exec --skip-git-repo-check --dangerously-bypass-approvals-and-sandbox -C {shlex.quote(str(engine.config.watchdog_codex_workdir))} -o "$LAST_MESSAGE_FILE" "$(cat \"$PROMPT_FILE\")")
        CMD_STR="$(printf '%q ' \"${{CMD[@]}}\")"
        exec timeout {engine.config.watchdog_codex_timeout_seconds} script -qefc "$CMD_STR" "$LOG_FILE"
        """
    )
    engine.codex_runner_file.write_text(codex_runner, encoding="utf-8")
    engine.codex_runner_file.chmod(0o755)

    codex_handoff = textwrap.dedent(
        f"""\
        #!/usr/bin/env bash
        set -euo pipefail
        nohup {shlex.quote(str(engine.codex_runner_file))} >/dev/null 2>&1 &
        echo $!
        """
    )
    engine.codex_handoff_file.write_text(codex_handoff, encoding="utf-8")
    engine.codex_handoff_file.chmod(0o755)

    opencode_runner = textwrap.dedent(
        f"""\
        #!/usr/bin/env bash
        set -euo pipefail
        cd {shlex.quote(str(engine.config.watchdog_opencode_fallback_workdir))}
        if [[ {shlex.quote(engine.config.watchdog_opencode_fallback_bin)} == */* ]]; then
          [[ -x {shlex.quote(engine.config.watchdog_opencode_fallback_bin)} ]] || {{ echo {shlex.quote(engine.config.watchdog_opencode_fallback_bin)}' CLI not found'; exit 127; }}
        else
          command -v {shlex.quote(engine.config.watchdog_opencode_fallback_bin)} >/dev/null 2>&1 || {{ echo {shlex.quote(engine.config.watchdog_opencode_fallback_bin)}' CLI not found in PATH'; exit 127; }}
        fi
        PROMPT_FILE={shlex.quote(str(engine.codex_prompt_file))}
        LOG_FILE={shlex.quote(str(engine.opencode_fallback_run_log_file))}
        CMD=({shlex.quote(engine.config.watchdog_opencode_fallback_bin)} run "$(cat \"$PROMPT_FILE\")")
        CMD_STR="$(printf '%q ' \"${{CMD[@]}}\")"
        exec timeout {engine.config.watchdog_opencode_fallback_timeout_seconds} script -qefc "$CMD_STR" "$LOG_FILE"
        """
    )
    engine.opencode_fallback_runner_file.write_text(opencode_runner, encoding="utf-8")
    engine.opencode_fallback_runner_file.chmod(0o755)

    opencode_handoff = textwrap.dedent(
        f"""\
        #!/usr/bin/env bash
        set -euo pipefail
        nohup {shlex.quote(str(engine.opencode_fallback_runner_file))} >/dev/null 2>&1 &
        echo $!
        """
    )
    engine.opencode_fallback_handoff_file.write_text(opencode_handoff, encoding="utf-8")
    engine.opencode_fallback_handoff_file.chmod(0o755)


def pid_is_alive(engine, pid: str) -> bool:
    if not pid.isdigit():
        return False
    try:
        os.kill(int(pid), 0)
        return True
    except OSError:
        return False


def trigger_opencode_fallback(engine, reason: str) -> None:
    if engine.incident_dir is None or engine.opencode_fallback_handoff_file is None or engine.opencode_fallback_run_log_file is None:
        engine.opencode_fallback_trigger_result = "incident-missing"
        return
    pid_file = engine.incident_dir / "opencode-fallback.pid"
    status_file = engine.incident_dir / "opencode-fallback-trigger-status.txt"
    if pid_file.exists():
        existing_pid = pid_file.read_text(encoding="utf-8").strip()
        if pid_is_alive(engine, existing_pid):
            engine.opencode_fallback_run_pid = existing_pid
            engine.opencode_fallback_trigger_result = "already-running"
            engine.write_opencode_fallback_status(status_file, engine.opencode_fallback_trigger_result, f"reason={reason} pid={existing_pid}")
            return
    if not engine.opencode_fallback_bin_available():
        engine.opencode_fallback_trigger_result = "opencode-missing"
        engine.write_opencode_fallback_status(
            status_file,
            engine.opencode_fallback_trigger_result,
            f"reason={reason} bin={engine.config.watchdog_opencode_fallback_bin}",
        )
        engine.log("WARN", f"opencode fallback unavailable: missing binary {engine.config.watchdog_opencode_fallback_bin}")
        return
    result = engine.run_command([str(engine.opencode_fallback_handoff_file)], timeout=10, merge_stderr=True)
    launched_pid = re.sub(r"\D", "", (result.output.splitlines()[-1] if result.output.strip() else ""))
    if pid_is_alive(engine, launched_pid):
        engine.opencode_fallback_run_pid = launched_pid
        engine.opencode_fallback_trigger_result = "launched"
        pid_file.write_text(f"{launched_pid}\n", encoding="utf-8")
        engine.write_opencode_fallback_status(
            status_file,
            engine.opencode_fallback_trigger_result,
            f"reason={reason} pid={launched_pid} log={engine.opencode_fallback_run_log_file}",
        )
        engine.log(
            "WARN",
            f"opencode fallback launched pid={launched_pid} log={engine.opencode_fallback_run_log_file} incident={engine.incident_id} reason={reason}",
        )
        return
    engine.opencode_fallback_trigger_result = "launch-failed"
    engine.write_opencode_fallback_status(status_file, engine.opencode_fallback_trigger_result, f"reason={reason}")
    engine.log("WARN", f"opencode fallback failed to launch incident={engine.incident_id} reason={reason}")


def trigger_codex_autorun(engine) -> None:
    if engine.incident_dir is None or engine.codex_handoff_file is None or engine.codex_run_log_file is None:
        engine.codex_trigger_result = "incident-missing"
        return
    pid_file = engine.incident_dir / "codex.pid"
    status_file = engine.incident_dir / "codex-trigger-status.txt"
    now_ts = int(time.time())
    if not engine.config.watchdog_enable_codex_autorun:
        engine.codex_trigger_result = "disabled"
        engine.write_codex_trigger_status(status_file, engine.codex_trigger_result, "codex autorun disabled")
        return
    if engine.config.watchdog_maintenance_file.exists():
        engine.codex_trigger_result = "maintenance-mode"
        engine.write_codex_trigger_status(
            status_file,
            engine.codex_trigger_result,
            f"maintenance_file={engine.config.watchdog_maintenance_file}",
        )
        engine.log("WARN", "codex autorun skipped: maintenance mode enabled")
        return
    if engine.consecutive_failures < engine.config.watchdog_codex_min_failures:
        engine.codex_trigger_result = "threshold-not-met"
        engine.write_codex_trigger_status(
            status_file,
            engine.codex_trigger_result,
            f"failures={engine.consecutive_failures} required={engine.config.watchdog_codex_min_failures}",
        )
        engine.log(
            "WARN",
            f"codex autorun skipped: failures={engine.consecutive_failures} required={engine.config.watchdog_codex_min_failures}",
        )
        return
    last_trigger = 0
    if engine.config.watchdog_codex_last_trigger_file.exists():
        try:
            last_trigger = int(engine.config.watchdog_codex_last_trigger_file.read_text(encoding="utf-8").strip())
        except ValueError:
            last_trigger = 0
    cooldown = engine.config.watchdog_codex_cooldown_seconds
    remaining = cooldown - (now_ts - last_trigger)
    if last_trigger > 0 and remaining > 0:
        engine.codex_trigger_result = "cooldown-active"
        engine.write_codex_trigger_status(status_file, engine.codex_trigger_result, f"remaining={remaining}")
        engine.log("WARN", "codex autorun skipped: cooldown active")
        return
    if pid_file.exists():
        existing_pid = pid_file.read_text(encoding="utf-8").strip()
        if pid_is_alive(engine, existing_pid):
            engine.codex_run_pid = existing_pid
            engine.codex_trigger_result = "already-running"
            engine.write_codex_trigger_status(status_file, engine.codex_trigger_result, f"pid={existing_pid}")
            return
    if not engine.codex_bin_available():
        trigger_opencode_fallback(engine, "codex-missing")
        engine.codex_trigger_result = f"codex-missing->{engine.opencode_fallback_trigger_result}"
        engine.write_codex_trigger_status(
            status_file,
            engine.codex_trigger_result,
            f"codex_bin={engine.config.watchdog_codex_bin} fallback_result={engine.opencode_fallback_trigger_result}",
        )
        engine.log(
            "WARN",
            f"codex autorun unavailable: missing binary {engine.config.watchdog_codex_bin}; fallback={engine.opencode_fallback_trigger_result}",
        )
        return
    result = engine.run_command([str(engine.codex_handoff_file)], timeout=10, merge_stderr=True)
    launched_pid = re.sub(r"\D", "", (result.output.splitlines()[-1] if result.output.strip() else ""))
    if pid_is_alive(engine, launched_pid):
        engine.codex_run_pid = launched_pid
        engine.codex_trigger_result = "launched"
        pid_file.write_text(f"{launched_pid}\n", encoding="utf-8")
        engine.config.watchdog_codex_last_trigger_file.write_text(f"{now_ts}\n", encoding="utf-8")
        engine.write_codex_trigger_status(status_file, engine.codex_trigger_result, f"pid={launched_pid} log={engine.codex_run_log_file}")
        engine.log("WARN", f"codex autorun launched pid={launched_pid} log={engine.codex_run_log_file} incident={engine.incident_id}")
        return
    trigger_opencode_fallback(engine, "codex-launch-failed")
    engine.codex_trigger_result = f"launch-failed->{engine.opencode_fallback_trigger_result}"
    engine.write_codex_trigger_status(
        status_file,
        engine.codex_trigger_result,
        f"codex_bin={engine.config.watchdog_codex_bin} fallback_result={engine.opencode_fallback_trigger_result}",
    )
    engine.log(
        "WARN",
        f"codex autorun failed to launch incident={engine.incident_id}; fallback={engine.opencode_fallback_trigger_result}",
    )


def collect_incident_bundle(
    engine,
    summary: str,
    doctor_output: str,
    active: str,
    main_pid: str,
    listeners: str,
) -> None:
    ensure_incident_context(engine)
    if engine.incident_dir is None:
        return
    engine.incident_dir.mkdir(parents=True, exist_ok=True)
    engine.update_incident_state("open", summary)
    (engine.incident_dir / "summary.txt").write_text(f"{summary}\n", encoding="utf-8")
    engine.write_incident_operator_summary(summary=summary, active=active, main_pid=main_pid, listeners=listeners)
    (engine.incident_dir / "doctor.out").write_text(doctor_output, encoding="utf-8")
    incident_meta_payload = {
        "incident_id": engine.incident_id,
        "time": engine.run_ts,
        "summary": summary,
        "active": active,
        "main_pid": main_pid,
        "listeners": listeners,
        "pre_repair_backup_result": engine.pre_repair_backup_result,
        "rollback_occurred": engine.rollback_occurred,
        "rollback_summary_archive_file": engine.rollback_summary_archive_file,
        "rollback_broken_config_file": engine.rollback_broken_config_file,
    }
    incident_meta = textwrap.dedent(
        f"""\
        incident_id={engine.incident_id}
        time={engine.run_ts}
        summary={summary}
        active={active}
        main_pid={main_pid}
        listeners={listeners}
        pre_repair_backup_result={engine.pre_repair_backup_result}
        rollback_occurred={'true' if engine.rollback_occurred else 'false'}
        rollback_summary_archive_file={engine.rollback_summary_archive_file}
        rollback_broken_config_file={engine.rollback_broken_config_file}
        """
    )
    (engine.incident_dir / "incident-meta.txt").write_text(incident_meta, encoding="utf-8")
    (engine.incident_dir / "incident-meta.json").write_text(
        json.dumps(incident_meta_payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    engine.run_capture_to_file(["openclaw", "status", "--json", "--timeout", "5000"], engine.incident_dir / "openclaw-status.json", timeout=15)
    engine.run_capture_to_file(["openclaw", "gateway", "status"], engine.incident_dir / "gateway-status.txt", timeout=15)
    engine.run_capture_to_file(
        ["systemctl", "--user", "status", engine.config.openclaw_gateway_service, "--no-pager"],
        engine.incident_dir / "systemctl-status.txt",
        timeout=20,
    )
    engine.run_capture_to_file(
        ["journalctl", "--user", "-u", engine.config.openclaw_gateway_service, "-n", "200", "--no-pager"],
        engine.incident_dir / "journal-tail.txt",
        timeout=20,
    )
    listeners_result = engine.run_command(["ss", "-tlnp"], timeout=15, merge_stderr=True)
    listener_lines = [
        line
        for line in listeners_result.output.splitlines()
        if f":{engine.config.openclaw_gateway_port}" in line
    ]
    (engine.incident_dir / "listeners.txt").write_text(
        "\n".join(listener_lines) + ("\n" if listener_lines else ""),
        encoding="utf-8",
    )
    if engine.config.watchdog_log_file.exists():
        tail_lines = engine.config.watchdog_log_file.read_text(encoding="utf-8", errors="replace").splitlines()[-200:]
        (engine.incident_dir / "watchdog-log-tail.txt").write_text("\n".join(tail_lines) + ("\n" if tail_lines else ""), encoding="utf-8")
    copy_if_exists(engine, engine.config.openclaw_config, engine.incident_dir / "current-openclaw.json")
    copy_if_exists(engine, engine.config.watchdog_last_good_config, engine.incident_dir / "last-good-openclaw.json")
    copy_if_exists(engine, engine.config.watchdog_last_rollback_summary_file, engine.incident_dir / "last-rollback-summary.txt")
    copy_if_exists(engine, engine.config.watchdog_event_file, engine.incident_dir / "last-event.txt")
    copy_if_exists(engine, engine.sibling_json_path(engine.config.watchdog_event_file), engine.incident_dir / "last-event.json")
    render_codex_prompt(engine, summary)
    engine.log("WARN", f"incident bundle prepared: id={engine.incident_id} dir={engine.incident_dir} prompt={engine.codex_prompt_file}")
