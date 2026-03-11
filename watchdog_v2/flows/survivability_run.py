from __future__ import annotations

from datetime import datetime

from watchdog_v2 import survival as survival_ops


def run(engine, ctx):
    from watchdog_v2.engine import RunOutcome

    start_ts = datetime.now().astimezone()
    engine.ctx.last_run_started_at = start_ts
    engine.ctx.run_ts = start_ts.strftime("%F %T %Z")
    engine.write_run_state({"last_run_started_at": start_ts.isoformat(timespec="seconds")})
    engine.log("INFO", "watchdog tick start (survivability flow)")
    engine.reset_recovery_tracking()
    last_good = engine.last_good_status()
    engine.ctx.last_good_validated_at = str(last_good.get("last_good_validated_at", "") or "")
    engine.ctx.last_good_generation_id = str(last_good.get("last_good_generation_id", "") or "")
    engine.ctx.last_good_generation_count = int(last_good.get("last_good_generation_count", 0) or 0)

    try:
        probe = engine.live_probe(include_doctor=True, apply_grace=True)
        engine.ctx.latest_probe = dict(probe)
        doctor_output = str(probe.get("doctor_output", ""))
        config_invalid = bool(probe.get("config_invalid", False))
        engine.sync_survival_mode(probe=probe, config_invalid=config_invalid)
        process_layer_healthy = bool(probe.get("process_layer_healthy", False))
        service_layer_healthy = bool(probe.get("service_layer_healthy", True))
        conversation_ready = bool(probe.get("conversation_ready", False))
        minimal_usable_ready = bool(probe.get("minimal_usable_ready", False))
        active = "true" if probe.get("service_active") else "false"
        main_pid = str(probe.get("service_main_pid", "0"))
        listeners = [str(item) for item in probe.get("listener_pids", [])]
        listeners_str = " ".join(listeners) if listeners else "none"
        engine.log(
            "INFO",
            f"survivability precheck active={active} main_pid={main_pid or '0'} listeners={listeners_str} "
            f"doctor_rc={probe.get('doctor_rc', 0)} service_probe={probe.get('service_probe_summary', 'n/a')} "
            f"conversation={probe.get('conversation_status', 'down')}",
        )

        run_state = engine.read_run_state()
        previous_service_probe_failures = int(run_state.get("service_probe_failures", 0) or 0)
        service_probe_failures = engine._service_probe_failures_for(probe, previous_service_probe_failures)
        service_probe_threshold_met = (
            engine.config.watchdog_enable_service_level_probe
            and process_layer_healthy
            and not service_layer_healthy
            and service_probe_failures >= engine.config.watchdog_service_level_failure_threshold
        )
        engine._write_probe_run_state(probe, config_invalid=config_invalid, service_probe_failures=service_probe_failures)

        if process_layer_healthy and conversation_ready and not config_invalid:
            engine.finalize_recovery_tracking(strategy="steady-state", restored_conversation=True)
            if not engine.ctx.survival_mode_active:
                engine.backup_last_good(validation=probe)
            summary = "conversation ready and gateway listener healthy"
            engine.set_state("healthy", summary)
            engine.log("INFO", "watchdog tick healthy (survivability flow)")
            return RunOutcome(exit_code=0, state="healthy", summary=summary)

        if process_layer_healthy and minimal_usable_ready and not config_invalid and not service_probe_threshold_met:
            engine.finalize_recovery_tracking(strategy="minimal-usable", restored_conversation=True)
            summary = f"minimal usable conversation only: {probe.get('conversation_probe_summary', 'n/a')}"
            engine.set_state("degraded", summary)
            engine.log("WARN", f"watchdog degraded without remediation: {summary}")
            return RunOutcome(exit_code=0, state="degraded", summary=summary)

        engine.record_recovery_step(
            "diagnose",
            "diagnosed",
            "config-invalid"
            if config_invalid
            else "process-down"
            if not process_layer_healthy
            else "service-threshold"
            if service_probe_threshold_met
            else str(probe.get("conversation_status", "down") or "down"),
        )
        drift = engine.drift_context()
        engine.ctx.config_drift_detected = bool(drift.get("detected", False))
        engine.ctx.drift_scope = [str(item) for item in drift.get("scope", []) if str(item).strip()]
        engine.ctx.drift_since_last_good = str(drift.get("since_last_good", "") or "")
        engine.ctx.drift_summary = str(drift.get("summary", "") or "")

        engine.run_pre_repair_backup()

        if config_invalid:
            engine.record_recovery_step("restart", "skipped", "config-invalid")
        else:
            if active != "true" and engine.listener_count() > 0:
                engine.kill_stray_listeners(main_pid)
            restart_ok = engine.restart_service()
            engine.record_recovery_step("restart", "success" if restart_ok else "failed", "systemctl")
            if restart_ok:
                restart_probe = engine.live_probe(include_doctor=True, apply_grace=True)
                engine.ctx.latest_probe = dict(restart_probe)
                doctor_output = str(restart_probe.get("doctor_output", doctor_output))
                config_invalid = bool(restart_probe.get("config_invalid", False))
                service_probe_failures = engine._service_probe_failures_for(restart_probe, service_probe_failures)
                engine._write_probe_run_state(restart_probe, config_invalid=config_invalid, service_probe_failures=service_probe_failures)
                if bool(restart_probe.get("minimal_usable_ready", False)):
                    engine.finalize_recovery_tracking(strategy="restart", restored_conversation=True)
                    if bool(restart_probe.get("conversation_ready", False)):
                        engine.backup_last_good(validation=restart_probe)
                    summary = (
                        "restart restored conversation readiness"
                        if bool(restart_probe.get("conversation_ready", False))
                        else "restart restored minimal usable conversation"
                    )
                    engine.set_state("recovered", summary)
                    engine.log("INFO", f"watchdog recovered via restart: {summary}")
                    return RunOutcome(exit_code=0, state="recovered", summary=summary)

        if engine.config.watchdog_last_good_config.exists() or engine.config.watchdog_last_good_manifest_file.exists():
            rollback_reason = (
                "config-invalid"
                if config_invalid
                else "config-drift"
                if engine.ctx.config_drift_detected
                else "restart-did-not-restore-conversation"
            )
            rollback_ok = engine.restore_last_good(reason=rollback_reason)
            engine.record_recovery_step(
                "rollback",
                "success" if rollback_ok else "failed",
                engine.ctx.rollback_candidate_used or rollback_reason,
            )
            if rollback_ok:
                rollback_restart_ok = engine.restart_service()
                engine.record_recovery_step("rollback-restart", "success" if rollback_restart_ok else "failed", "systemctl")
                if rollback_restart_ok:
                    rollback_probe = engine.live_probe(include_doctor=True, apply_grace=True)
                    engine.ctx.latest_probe = dict(rollback_probe)
                    doctor_output = str(rollback_probe.get("doctor_output", doctor_output))
                    config_invalid = bool(rollback_probe.get("config_invalid", False))
                    service_probe_failures = engine._service_probe_failures_for(rollback_probe, service_probe_failures)
                    engine._write_probe_run_state(rollback_probe, config_invalid=config_invalid, service_probe_failures=service_probe_failures)
                    if bool(rollback_probe.get("minimal_usable_ready", False)):
                        engine.finalize_recovery_tracking(strategy="rollback", restored_conversation=True)
                        if bool(rollback_probe.get("conversation_ready", False)):
                            engine.backup_last_good(validation=rollback_probe)
                        summary = (
                            f"rollback restored conversation readiness (candidate={engine.ctx.rollback_candidate_used or 'unknown'})"
                            if bool(rollback_probe.get("conversation_ready", False))
                            else f"rollback restored minimal usable conversation (candidate={engine.ctx.rollback_candidate_used or 'unknown'})"
                        )
                        engine.set_state("recovered", summary)
                        engine.log("INFO", f"watchdog recovered via rollback: {summary}")
                        return RunOutcome(exit_code=0, state="recovered", summary=summary)
        else:
            engine.record_recovery_step("rollback", "skipped", "no-last-good")

        survival_reason = (
            "config-invalid"
            if config_invalid
            else "config-drift"
            if engine.ctx.config_drift_detected
            else str(probe.get("conversation_status", "down") or "down")
        )
        survival_result = engine.enter_survival_mode(reason=survival_reason)
        if bool(survival_result.get("applied", False)):
            engine.record_recovery_step("survival", "success", survival_reason)
            survival_restart_ok = engine.restart_service()
            engine.record_recovery_step("survival-restart", "success" if survival_restart_ok else "failed", "systemctl")
            if survival_restart_ok:
                survival_probe = engine.live_probe(include_doctor=True, apply_grace=True)
                engine.ctx.latest_probe = dict(survival_probe)
                doctor_output = str(survival_probe.get("doctor_output", doctor_output))
                config_invalid = bool(survival_probe.get("config_invalid", False))
                service_probe_failures = engine._service_probe_failures_for(survival_probe, service_probe_failures)
                engine._write_probe_run_state(survival_probe, config_invalid=config_invalid, service_probe_failures=service_probe_failures)
                if bool(survival_probe.get("minimal_usable_ready", False)):
                    engine.finalize_recovery_tracking(strategy="survival", restored_conversation=True)
                    summary = (
                        "survival mode restored conversation readiness"
                        if bool(survival_probe.get("conversation_ready", False))
                        else "survival mode restored minimal usable conversation"
                    )
                    engine.set_state("recovered", summary, health_level_override="degraded")
                    engine.log("WARN", f"watchdog recovered via survival mode: {summary}")
                    return RunOutcome(exit_code=0, state="recovered", summary=summary)
        else:
            engine.record_recovery_step("survival", "skipped", str(survival_result.get("detail", "not-applicable") or "not-applicable"))

        if engine.config.watchdog_enable_doctor_repair:
            engine.run_doctor_repair()
            engine.record_recovery_step("doctor", "success", "repair-ran")
            doctor_restart_ok = engine.restart_service()
            engine.record_recovery_step("doctor-restart", "success" if doctor_restart_ok else "failed", "systemctl")
            if doctor_restart_ok:
                doctor_probe = engine.live_probe(include_doctor=True, apply_grace=True)
                engine.ctx.latest_probe = dict(doctor_probe)
                doctor_output = str(doctor_probe.get("doctor_output", doctor_output))
                config_invalid = bool(doctor_probe.get("config_invalid", False))
                service_probe_failures = engine._service_probe_failures_for(doctor_probe, service_probe_failures)
                engine._write_probe_run_state(doctor_probe, config_invalid=config_invalid, service_probe_failures=service_probe_failures)
                if bool(doctor_probe.get("minimal_usable_ready", False)):
                    engine.finalize_recovery_tracking(strategy="doctor", restored_conversation=True)
                    if bool(doctor_probe.get("conversation_ready", False)):
                        engine.backup_last_good(validation=doctor_probe)
                    summary = (
                        "doctor repair restored conversation readiness"
                        if bool(doctor_probe.get("conversation_ready", False))
                        else "doctor repair restored minimal usable conversation"
                    )
                    engine.set_state("recovered", summary)
                    engine.log("INFO", f"watchdog recovered via doctor repair: {summary}")
                    return RunOutcome(exit_code=0, state="recovered", summary=summary)
        else:
            engine.record_recovery_step("doctor", "skipped", "disabled")

        final_probe = dict(engine.ctx.latest_probe) if engine.ctx.latest_probe else engine.live_probe(include_doctor=False, apply_grace=True)
        final_process_layer_healthy = bool(final_probe.get("process_layer_healthy", False))
        final_service_layer_healthy = bool(final_probe.get("service_layer_healthy", True))
        final_active = "true" if final_probe.get("service_active") else "false"
        final_pid = str(final_probe.get("service_main_pid", "0"))
        final_listeners = [str(item) for item in final_probe.get("listener_pids", [])]
        final_listeners_str = " ".join(final_listeners) if final_listeners else "none"
        final_summary = (
            f"conversation={final_probe.get('conversation_status', 'down')} active={final_active} main_pid={final_pid or '0'} "
            f"listeners={final_listeners_str} service_probe={final_probe.get('service_probe_summary', 'n/a')} "
            f"recovery_path={engine.recovery_path_text()}"
        )

        engine.finalize_recovery_tracking(strategy="escalated", restored_conversation=False)
        engine.increment_failure_count()
        engine.write_run_state(
            {
                "service_probe_failures": service_probe_failures if final_process_layer_healthy and not final_service_layer_healthy else 0,
                "last_service_probe_at": str(final_probe.get("service_probe_checked_at", engine.now_iso())),
                "last_service_probe_result": "healthy" if final_service_layer_healthy else "degraded",
                "last_service_probe_summary": str(final_probe.get("service_probe_summary", "")),
                "last_service_probe_rc": int(final_probe.get("service_probe_rc", 0) or 0),
                "health_level": "failed",
                "current_mode": engine.current_mode(maintenance=engine.config.watchdog_maintenance_file.exists(), survival=engine.ctx.survival_mode_active),
                "cooldown_remaining_seconds": engine.codex_cooldown_remaining(),
                "conversation_ready": bool(final_probe.get("conversation_ready", False)),
                "minimal_usable_ready": bool(final_probe.get("minimal_usable_ready", False)),
                "conversation_status": str(final_probe.get("conversation_status", "down") or "down"),
                "conversation_probe_summary": str(final_probe.get("conversation_probe_summary", "") or ""),
                "last_recovery_strategy": engine.ctx.last_recovery_strategy,
                "last_recovery_path": engine.recovery_path_text(),
                "last_recovery_action_count": engine.ctx.last_recovery_action_count,
                "last_recovery_restored_conversation": engine.ctx.last_recovery_restored_conversation,
                "rollback_candidate_used": engine.ctx.rollback_candidate_used,
                "rollback_reason": engine.ctx.rollback_reason,
                "config_drift_detected": engine.ctx.config_drift_detected,
                "drift_scope": list(engine.ctx.drift_scope),
                "drift_since_last_good": engine.ctx.drift_since_last_good,
                "drift_summary": engine.ctx.drift_summary,
                **survival_ops.run_state_fields(self),
                **engine.guard_status(),
            }
        )
        engine.collect_incident_bundle(
            f"survivability remediation failed: {final_summary}",
            doctor_output,
            final_active,
            final_pid,
            final_listeners_str,
        )
        engine.trigger_codex_autorun()
        engine.write_incident_operator_summary(
            summary=f"survivability remediation failed: {final_summary}",
            active=final_active,
            main_pid=final_pid,
            listeners=final_listeners_str,
        )
        summary = (
            f"{final_summary}；incident={engine.ctx.incident_dir or 'none'}；"
            f"codex_handoff={engine.ctx.codex_handoff_file or 'none'}；codex_result={engine.ctx.codex_trigger_result or 'not-run'}"
        )
        engine.set_state("failed", summary)
        engine.log(
            "ERROR",
            f"watchdog failed to recover: {final_summary} incident={engine.ctx.incident_dir or 'none'} codex={engine.ctx.codex_trigger_result or 'not-run'}",
        )
        return RunOutcome(exit_code=1, state="failed", summary=summary)
    finally:
        finish_ts = datetime.now().astimezone()
        engine.ctx.last_run_finished_at = finish_ts
        duration_ms = max(0, int((finish_ts - start_ts).total_seconds() * 1000))
        engine.write_run_state(
            {
                "last_run_finished_at": finish_ts.isoformat(timespec="seconds"),
                "last_run_duration_ms": duration_ms,
            }
        )

