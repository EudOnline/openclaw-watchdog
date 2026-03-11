from __future__ import annotations

from datetime import datetime

from watchdog_v2 import survival as survival_ops


def run(engine, ctx):
    from watchdog_v2.engine import RunOutcome

    start_ts = datetime.now().astimezone()
    engine.last_run_started_at = start_ts
    engine.run_ts = start_ts.strftime("%F %T %Z")
    engine.write_run_state({"last_run_started_at": start_ts.isoformat(timespec="seconds")})
    engine.log("INFO", "watchdog tick start")

    try:
        probe = engine.live_probe(include_doctor=True, apply_grace=True)
        doctor_output = str(probe.get("doctor_output", ""))
        config_invalid = bool(probe.get("config_invalid", False))
        process_layer_healthy = bool(probe.get("process_layer_healthy", False))
        service_layer_healthy = bool(probe.get("service_layer_healthy", True))
        active = "true" if probe.get("service_active") else "false"
        main_pid = str(probe.get("service_main_pid", "0"))
        listeners = [str(item) for item in probe.get("listener_pids", [])]
        listeners_str = " ".join(listeners) if listeners else "none"
        engine.log(
            "INFO",
            f"precheck active={active} main_pid={main_pid or '0'} listeners={listeners_str} "
            f"doctor_rc={probe.get('doctor_rc', 0)} service_probe={probe.get('service_probe_summary', 'n/a')}",
        )

        run_state = engine.read_run_state()
        previous_service_probe_failures = int(run_state.get("service_probe_failures", 0) or 0)
        if engine.config.watchdog_enable_service_level_probe and process_layer_healthy and not service_layer_healthy:
            service_probe_failures = previous_service_probe_failures + 1
        else:
            service_probe_failures = 0
        service_probe_threshold_met = (
            engine.config.watchdog_enable_service_level_probe
            and process_layer_healthy
            and not service_layer_healthy
            and service_probe_failures >= engine.config.watchdog_service_level_failure_threshold
        )
        initial_health_level = "healthy"
        if config_invalid or not process_layer_healthy:
            initial_health_level = "failed"
        elif process_layer_healthy and not service_layer_healthy:
            initial_health_level = "degraded"
        engine.write_run_state(
            {
                "service_probe_failures": service_probe_failures,
                "last_service_probe_at": str(probe.get("service_probe_checked_at", engine.now_iso())),
                "last_service_probe_result": "healthy" if service_layer_healthy else "degraded",
                "last_service_probe_summary": str(probe.get("service_probe_summary", "")),
                "last_service_probe_rc": int(probe.get("service_probe_rc", 0) or 0),
                "health_level": initial_health_level,
                "current_mode": engine.current_mode(
                    maintenance=engine.config.watchdog_maintenance_file.exists(),
                    degraded=initial_health_level == "degraded",
                ),
                "cooldown_remaining_seconds": engine.codex_cooldown_remaining(),
            }
        )

        need_remediation = config_invalid or not process_layer_healthy or service_probe_threshold_met
        if need_remediation:
            engine.run_pre_repair_backup()

        if config_invalid:
            engine.log("WARN", "detected invalid OpenClaw config")
            if engine.restore_last_good():
                engine.restart_service()
                probe = engine.live_probe(include_doctor=True, apply_grace=True)
                doctor_output = str(probe.get("doctor_output", doctor_output))
                config_invalid = bool(probe.get("config_invalid", False))
                process_layer_healthy = bool(probe.get("process_layer_healthy", False))
                service_layer_healthy = bool(probe.get("service_layer_healthy", True))
                active = "true" if probe.get("service_active") else "false"
                main_pid = str(probe.get("service_main_pid", "0"))
                listeners = [str(item) for item in probe.get("listener_pids", [])]
                listeners_str = " ".join(listeners) if listeners else "none"
                if engine.config.watchdog_enable_service_level_probe and process_layer_healthy and not service_layer_healthy:
                    service_probe_failures += 1
                    engine.write_run_state(
                        {
                            "service_probe_failures": service_probe_failures,
                            "last_service_probe_at": str(probe.get("service_probe_checked_at", engine.now_iso())),
                            "last_service_probe_result": "healthy" if service_layer_healthy else "degraded",
                            "last_service_probe_summary": str(probe.get("service_probe_summary", "")),
                            "last_service_probe_rc": int(probe.get("service_probe_rc", 0) or 0),
                        }
                    )
            else:
                engine.increment_failure_count()
                engine.collect_incident_bundle("配置无效，且没有 last-good 备份可恢复", doctor_output, active, main_pid, listeners_str)
                engine.trigger_codex_autorun()
                engine.write_incident_operator_summary(
                    summary="配置无效，且没有 last-good 备份可恢复",
                    active=active,
                    main_pid=main_pid,
                    listeners=listeners_str,
                )
                summary = (
                    f"配置无效，且没有 last-good；incident={engine.incident_dir or 'none'}；"
                    f"codex_handoff={engine.codex_handoff_file or 'none'}；codex_result={engine.codex_trigger_result or 'not-run'}"
                )
                engine.set_state("failed", summary)
                return RunOutcome(exit_code=1, state="failed", summary=summary)

        if process_layer_healthy and service_layer_healthy:
            engine.backup_last_good()
            engine.write_run_state({"service_probe_failures": 0})
            summary = "service active and listener matches service process tree"
            engine.set_state("healthy", summary)
            engine.log("INFO", "watchdog tick healthy")
            return RunOutcome(exit_code=0, state="healthy", summary=summary)

        if process_layer_healthy and not service_layer_healthy and not service_probe_threshold_met:
            summary = (
                f"service layer degraded: {probe.get('service_probe_summary', 'status probe failed')} "
                f"({service_probe_failures}/{engine.config.watchdog_service_level_failure_threshold})"
            )
            engine.set_state("degraded", summary)
            engine.log("WARN", f"watchdog degraded without remediation: {summary}")
            return RunOutcome(exit_code=0, state="degraded", summary=summary)

        if active != "true" and engine.listener_count() > 0:
            engine.kill_stray_listeners(main_pid)

        engine.run_doctor_repair()
        engine.restart_service()

        final_probe = engine.live_probe(include_doctor=False, apply_grace=True)
        final_process_layer_healthy = bool(final_probe.get("process_layer_healthy", False))
        final_service_layer_healthy = bool(final_probe.get("service_layer_healthy", True))
        if final_process_layer_healthy and final_service_layer_healthy:
            engine.backup_last_good()
            engine.write_run_state(
                {
                    "service_probe_failures": 0,
                    "last_service_probe_at": str(final_probe.get("service_probe_checked_at", engine.now_iso())),
                    "last_service_probe_result": "healthy",
                    "last_service_probe_summary": str(final_probe.get("service_probe_summary", "")),
                    "last_service_probe_rc": int(final_probe.get("service_probe_rc", 0) or 0),
                }
            )
            summary = "watchdog restarted gateway successfully"
            engine.set_state("recovered", summary)
            engine.log("INFO", "watchdog recovered service")
            return RunOutcome(exit_code=0, state="recovered", summary=summary)

        final_active = "true" if final_probe.get("service_active") else "false"
        final_pid = str(final_probe.get("service_main_pid", "0"))
        final_listeners = [str(item) for item in final_probe.get("listener_pids", [])]
        final_listeners_str = " ".join(final_listeners) if final_listeners else "none"
        final_summary = (
            f"active={final_active} main_pid={final_pid or '0'} listeners={final_listeners_str} "
            f"service_probe={final_probe.get('service_probe_summary', 'n/a')}"
        )

        engine.increment_failure_count()
        engine.write_run_state(
            {
                "service_probe_failures": service_probe_failures if final_process_layer_healthy and not final_service_layer_healthy else 0,
                "last_service_probe_at": str(final_probe.get("service_probe_checked_at", engine.now_iso())),
                "last_service_probe_result": "healthy" if final_service_layer_healthy else "degraded",
                "last_service_probe_summary": str(final_probe.get("service_probe_summary", "")),
                "last_service_probe_rc": int(final_probe.get("service_probe_rc", 0) or 0),
                "health_level": "failed",
                "current_mode": engine.current_mode(maintenance=engine.config.watchdog_maintenance_file.exists()),
                "cooldown_remaining_seconds": engine.codex_cooldown_remaining(),
            }
        )
        engine.collect_incident_bundle(
            f"deterministic remediation failed: {final_summary}",
            doctor_output,
            final_active,
            final_pid,
            final_listeners_str,
        )
        engine.trigger_codex_autorun()
        engine.write_incident_operator_summary(
            summary=f"deterministic remediation failed: {final_summary}",
            active=final_active,
            main_pid=final_pid,
            listeners=final_listeners_str,
        )
        summary = (
            f"{final_summary}；incident={engine.incident_dir or 'none'}；"
            f"codex_handoff={engine.codex_handoff_file or 'none'}；codex_result={engine.codex_trigger_result or 'not-run'}"
        )
        engine.set_state("failed", summary)
        engine.log(
            "ERROR",
            f"watchdog failed to recover: {final_summary} incident={engine.incident_dir or 'none'} codex={engine.codex_trigger_result or 'not-run'}",
        )
        return RunOutcome(exit_code=1, state="failed", summary=summary)
    finally:
        finish_ts = datetime.now().astimezone()
        engine.last_run_finished_at = finish_ts
        duration_ms = max(0, int((finish_ts - start_ts).total_seconds() * 1000))
        engine.write_run_state(
            {
                "last_run_finished_at": finish_ts.isoformat(timespec="seconds"),
                "last_run_duration_ms": duration_ms,
            }
        )

