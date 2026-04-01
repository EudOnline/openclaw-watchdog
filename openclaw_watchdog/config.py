from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def default_env_file() -> Path:
    return repo_root() / "config" / "openclaw-watchdog.env"


def _strip_quotes(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        return value[1:-1]
    return value


def parse_env_file(path: Path | None) -> dict[str, str]:
    values: dict[str, str] = {}
    if path is None or not path.exists():
        return values
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].lstrip()
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = _strip_quotes(value.strip())
        if key:
            values[key] = value
    return values


def _env(raw: dict[str, str], key: str, default: str) -> str:
    return os.environ.get(key, raw.get(key, default))


def _env_bool(raw: dict[str, str], key: str, default: bool) -> bool:
    value = _env(raw, key, "true" if default else "false").strip().lower()
    return value in {"1", "true", "yes", "on"}


def _env_int(raw: dict[str, str], key: str, default: int) -> int:
    value = _env(raw, key, str(default)).strip()
    try:
        return int(value)
    except ValueError:
        return default


def _env_path(raw: dict[str, str], key: str, default: str) -> Path:
    return Path(_env(raw, key, default)).expanduser()


def _env_optional_path(raw: dict[str, str], key: str) -> Path | None:
    value = _env(raw, key, "").strip()
    if not value:
        return None
    return Path(value).expanduser()


def _env_csv(raw: dict[str, str], key: str, default: str) -> tuple[str, ...]:
    value = _env(raw, key, default)
    parts = [item.strip() for item in value.split(",")]
    return tuple(item for item in parts if item)


@dataclass(frozen=True)
class Config:
    repo_root: Path
    env_file: Path | None
    openclaw_config: Path
    opencode_bootstrap_config_path: Path
    opencode_bootstrap_model: str
    openclaw_bootstrap_timeout_seconds: int
    openclaw_bootstrap_log_file: Path | None
    openclaw_bootstrap_qqbot_app_id: str
    openclaw_bootstrap_qqbot_client_secret: str
    openclaw_bootstrap_feishu_app_id: str
    openclaw_bootstrap_feishu_app_secret: str
    openclaw_bootstrap_feishu_bot_name: str
    openclaw_gateway_port: int
    openclaw_gateway_service: str
    watchdog_state_dir: Path
    watchdog_log_file: Path
    watchdog_event_file: Path
    watchdog_event_history_file: Path
    watchdog_event_history_limit: int
    watchdog_run_state_file: Path
    watchdog_last_good_config: Path
    watchdog_last_rollback_summary_file: Path
    watchdog_rollback_archive_dir: Path
    watchdog_incidents_dir: Path
    watchdog_incident_index_file: Path
    watchdog_incident_index_limit: int
    watchdog_last_report_file: Path
    watchdog_last_metrics_file: Path
    watchdog_failure_count_file: Path
    watchdog_maintenance_file: Path
    watchdog_lock_file: Path
    watchdog_notify_channel: str
    watchdog_notify_target: str
    watchdog_notify_account: str
    watchdog_notify_on_degraded: bool
    watchdog_notify_on_recovery: bool
    watchdog_notify_on_failure: bool
    watchdog_restart_wait_seconds: int
    watchdog_active_no_listener_grace_seconds: int
    watchdog_enable_service_level_probe: bool
    watchdog_enable_conversation_probe: bool
    watchdog_primary_conversation_targets: tuple[str, ...]
    watchdog_minimal_usable_allow_optional_failures: bool
    watchdog_service_level_timeout_seconds: int
    watchdog_service_level_retry_grace_seconds: int
    watchdog_service_level_failure_threshold: int
    watchdog_enable_model_http_error_failover: bool
    watchdog_model_http_error_threshold: int
    watchdog_model_http_error_window_minutes: int
    watchdog_model_http_error_cooldown_seconds: int
    watchdog_model_failover_max_applies_per_day: int
    watchdog_model_http_error_logs_limit: int
    watchdog_model_http_error_log_max_bytes: int
    watchdog_enable_survivability_flow: bool
    watchdog_enable_survival_mode: bool
    watchdog_survival_config_file: Path
    watchdog_survival_state_file: Path
    watchdog_survival_required_channels: tuple[str, ...]
    watchdog_survival_disable_optional_extensions: bool
    watchdog_survival_stable_ready_runs: int
    watchdog_message_timeout_seconds: int
    watchdog_enable_message_loop_probe: bool
    watchdog_message_loop_probe_account: str
    watchdog_message_loop_probe_channel: str
    watchdog_message_loop_probe_target: str
    watchdog_message_loop_probe_reply_from: str
    watchdog_message_loop_probe_events_file: Path
    watchdog_message_loop_probe_timeout_seconds: int
    watchdog_message_loop_probe_cooldown_seconds: int
    watchdog_doctor_timeout_seconds: int
    watchdog_enable_doctor_repair: bool
    watchdog_enable_pre_repair_backup: bool
    watchdog_backup_script: Path
    watchdog_backup_env_file: Path
    watchdog_backup_timeout_seconds: int
    watchdog_keep_rollbacks: int
    watchdog_last_good_manifest_file: Path
    watchdog_last_good_generations: int
    watchdog_guard_manifest_file: Path
    watchdog_protected_paths: tuple[str, ...]
    watchdog_enable_drift_auto_rollback: bool
    watchdog_keep_incidents: int
    watchdog_codex_bin: str
    watchdog_codex_model_hint: str
    watchdog_codex_workdir: Path
    watchdog_codex_timeout_seconds: int
    watchdog_claude_code_bin: str
    watchdog_claude_code_workdir: Path
    watchdog_claude_code_timeout_seconds: int
    watchdog_gemini_cli_bin: str
    watchdog_gemini_cli_workdir: Path
    watchdog_gemini_cli_timeout_seconds: int
    watchdog_opencode_bin: str
    watchdog_opencode_workdir: Path
    watchdog_opencode_timeout_seconds: int
    watchdog_litellm_enabled: bool
    watchdog_litellm_model: str
    watchdog_litellm_api_base: str
    watchdog_litellm_api_key_env: str
    watchdog_litellm_timeout_seconds: int
    watchdog_rescue_knowledge_root: Path
    watchdog_rescue_cases_dir: Path
    watchdog_rescue_candidate_rules_dir: Path
    watchdog_rescue_rules_dir: Path
    watchdog_rescue_reviews_dir: Path
    watchdog_rescue_editable_paths: tuple[str, ...]
    watchdog_rescue_editable_keys: tuple[str, ...]

    @classmethod
    def load(cls, env_file: Path | None = None) -> "Config":
        root = repo_root()
        candidate = env_file if env_file is not None else default_env_file()
        raw = parse_env_file(candidate)
        resolved_env_file = candidate if candidate.exists() else None
        return cls(
            repo_root=root,
            env_file=resolved_env_file,
            openclaw_config=_env_path(raw, "OPENCLAW_CONFIG", "~/.openclaw/openclaw.json"),
            opencode_bootstrap_config_path=_env_path(
                raw,
                "OPENCODE_BOOTSTRAP_CONFIG_PATH",
                _env(raw, "OPENCODE_CONFIG", "~/.config/opencode/opencode.json"),
            ),
            opencode_bootstrap_model=(
                _env(raw, "OPENCODE_BOOTSTRAP_MODEL", "opencode/minimax-m2.5-free").strip()
                or "opencode/minimax-m2.5-free"
            ),
            openclaw_bootstrap_timeout_seconds=max(10, _env_int(raw, "OPENCLAW_BOOTSTRAP_TIMEOUT_SECONDS", 600)),
            openclaw_bootstrap_log_file=_env_optional_path(raw, "OPENCLAW_BOOTSTRAP_LOG_FILE"),
            openclaw_bootstrap_qqbot_app_id=_env(raw, "OPENCLAW_BOOTSTRAP_QQBOT_APP_ID", _env(raw, "QQBOT_APP_ID", "")).strip(),
            openclaw_bootstrap_qqbot_client_secret=_env(
                raw,
                "OPENCLAW_BOOTSTRAP_QQBOT_CLIENT_SECRET",
                _env(raw, "QQBOT_CLIENT_SECRET", ""),
            ).strip(),
            openclaw_bootstrap_feishu_app_id=_env(
                raw,
                "OPENCLAW_BOOTSTRAP_FEISHU_APP_ID",
                _env(raw, "FEISHU_APP_ID", ""),
            ).strip(),
            openclaw_bootstrap_feishu_app_secret=_env(
                raw,
                "OPENCLAW_BOOTSTRAP_FEISHU_APP_SECRET",
                _env(raw, "FEISHU_APP_SECRET", ""),
            ).strip(),
            openclaw_bootstrap_feishu_bot_name=_env(raw, "OPENCLAW_BOOTSTRAP_FEISHU_BOT_NAME", "OpenClaw"),
            openclaw_gateway_port=_env_int(raw, "OPENCLAW_GATEWAY_PORT", 18789),
            openclaw_gateway_service=_env(raw, "OPENCLAW_GATEWAY_SERVICE", "openclaw-gateway.service"),
            watchdog_state_dir=_env_path(raw, "WATCHDOG_STATE_DIR", "~/.openclaw-backup/watchdog"),
            watchdog_log_file=_env_path(raw, "WATCHDOG_LOG_FILE", "~/.openclaw-backup/watchdog/watchdog.log"),
            watchdog_event_file=_env_path(raw, "WATCHDOG_EVENT_FILE", "~/.openclaw-backup/watchdog/last-event.txt"),
            watchdog_event_history_file=_env_path(raw, "WATCHDOG_EVENT_HISTORY_FILE", "~/.openclaw-backup/watchdog/event-history.jsonl"),
            watchdog_event_history_limit=max(1, _env_int(raw, "WATCHDOG_EVENT_HISTORY_LIMIT", 20)),
            watchdog_run_state_file=_env_path(raw, "WATCHDOG_RUN_STATE_FILE", "~/.openclaw-backup/watchdog/run-state.json"),
            watchdog_last_good_config=_env_path(raw, "WATCHDOG_LAST_GOOD_CONFIG", "~/.openclaw-backup/watchdog/openclaw.last-good.json"),
            watchdog_last_rollback_summary_file=_env_path(raw, "WATCHDOG_LAST_ROLLBACK_SUMMARY_FILE", "~/.openclaw-backup/watchdog/last-rollback-summary.txt"),
            watchdog_rollback_archive_dir=_env_path(raw, "WATCHDOG_ROLLBACK_ARCHIVE_DIR", "~/.openclaw-backup/watchdog/rollback-archives"),
            watchdog_incidents_dir=_env_path(raw, "WATCHDOG_INCIDENTS_DIR", "~/.openclaw-backup/watchdog/incidents"),
            watchdog_incident_index_file=_env_path(raw, "WATCHDOG_INCIDENT_INDEX_FILE", "~/.openclaw-backup/watchdog/incident-index.json"),
            watchdog_incident_index_limit=max(1, _env_int(raw, "WATCHDOG_INCIDENT_INDEX_LIMIT", 20)),
            watchdog_last_report_file=_env_path(raw, "WATCHDOG_LAST_REPORT_FILE", "~/.openclaw-backup/watchdog/last-report.json"),
            watchdog_last_metrics_file=_env_path(raw, "WATCHDOG_LAST_METRICS_FILE", "~/.openclaw-backup/watchdog/last-metrics.json"),
            watchdog_failure_count_file=_env_path(raw, "WATCHDOG_FAILURE_COUNT_FILE", "~/.openclaw-backup/watchdog/consecutive-failures"),
            watchdog_maintenance_file=_env_path(raw, "WATCHDOG_MAINTENANCE_FILE", "~/.openclaw-backup/watchdog/maintenance-mode"),
            watchdog_lock_file=_env_path(raw, "WATCHDOG_LOCK_FILE", "~/.openclaw-backup/watchdog/watchdog.lock"),
            watchdog_notify_channel=_env(raw, "WATCHDOG_NOTIFY_CHANNEL", ""),
            watchdog_notify_target=_env(raw, "WATCHDOG_NOTIFY_TARGET", ""),
            watchdog_notify_account=_env(raw, "WATCHDOG_NOTIFY_ACCOUNT", "default"),
            watchdog_notify_on_degraded=_env_bool(raw, "WATCHDOG_NOTIFY_ON_DEGRADED", True),
            watchdog_notify_on_recovery=_env_bool(raw, "WATCHDOG_NOTIFY_ON_RECOVERY", True),
            watchdog_notify_on_failure=_env_bool(raw, "WATCHDOG_NOTIFY_ON_FAILURE", True),
            watchdog_restart_wait_seconds=_env_int(raw, "WATCHDOG_RESTART_WAIT_SECONDS", 12),
            watchdog_active_no_listener_grace_seconds=max(0, _env_int(raw, "WATCHDOG_ACTIVE_NO_LISTENER_GRACE_SECONDS", 30)),
            watchdog_enable_service_level_probe=_env_bool(raw, "WATCHDOG_ENABLE_SERVICE_LEVEL_PROBE", True),
            watchdog_enable_conversation_probe=_env_bool(raw, "WATCHDOG_ENABLE_CONVERSATION_PROBE", True),
            watchdog_primary_conversation_targets=_env_csv(raw, "WATCHDOG_PRIMARY_CONVERSATION_TARGETS", "gateway,channels"),
            watchdog_minimal_usable_allow_optional_failures=_env_bool(raw, "WATCHDOG_MINIMAL_USABLE_ALLOW_OPTIONAL_FAILURES", True),
            watchdog_service_level_timeout_seconds=max(1, _env_int(raw, "WATCHDOG_SERVICE_LEVEL_TIMEOUT_SECONDS", 12)),
            watchdog_service_level_retry_grace_seconds=max(0, _env_int(raw, "WATCHDOG_SERVICE_LEVEL_RETRY_GRACE_SECONDS", 60)),
            watchdog_service_level_failure_threshold=max(1, _env_int(raw, "WATCHDOG_SERVICE_LEVEL_FAILURE_THRESHOLD", 6)),
            watchdog_enable_model_http_error_failover=_env_bool(raw, "WATCHDOG_ENABLE_MODEL_HTTP_ERROR_FAILOVER", False),
            watchdog_model_http_error_threshold=max(1, _env_int(raw, "WATCHDOG_MODEL_HTTP_ERROR_THRESHOLD", 3)),
            watchdog_model_http_error_window_minutes=max(1, _env_int(raw, "WATCHDOG_MODEL_HTTP_ERROR_WINDOW_MINUTES", 15)),
            watchdog_model_http_error_cooldown_seconds=max(0, _env_int(raw, "WATCHDOG_MODEL_HTTP_ERROR_COOLDOWN_SECONDS", 1800)),
            watchdog_model_failover_max_applies_per_day=max(0, _env_int(raw, "WATCHDOG_MODEL_FAILOVER_MAX_APPLIES_PER_DAY", 3)),
            watchdog_model_http_error_logs_limit=max(20, _env_int(raw, "WATCHDOG_MODEL_HTTP_ERROR_LOGS_LIMIT", 200)),
            watchdog_model_http_error_log_max_bytes=max(4096, _env_int(raw, "WATCHDOG_MODEL_HTTP_ERROR_LOG_MAX_BYTES", 262144)),
            watchdog_enable_survivability_flow=_env_bool(raw, "WATCHDOG_ENABLE_SURVIVABILITY_FLOW", False),
            watchdog_enable_survival_mode=_env_bool(raw, "WATCHDOG_ENABLE_SURVIVAL_MODE", False),
            watchdog_survival_config_file=_env_path(raw, "WATCHDOG_SURVIVAL_CONFIG_FILE", "~/.openclaw-backup/watchdog/openclaw.survival.json"),
            watchdog_survival_state_file=_env_path(raw, "WATCHDOG_SURVIVAL_STATE_FILE", "~/.openclaw-backup/watchdog/survival-mode.json"),
            watchdog_survival_required_channels=_env_csv(raw, "WATCHDOG_SURVIVAL_REQUIRED_CHANNELS", "qqbot"),
            watchdog_survival_disable_optional_extensions=_env_bool(raw, "WATCHDOG_SURVIVAL_DISABLE_OPTIONAL_EXTENSIONS", False),
            watchdog_survival_stable_ready_runs=max(1, _env_int(raw, "WATCHDOG_SURVIVAL_STABLE_READY_RUNS", 2)),
            watchdog_message_timeout_seconds=_env_int(raw, "WATCHDOG_MESSAGE_TIMEOUT_SECONDS", 20),
            watchdog_enable_message_loop_probe=_env_bool(raw, "WATCHDOG_ENABLE_MESSAGE_LOOP_PROBE", False),
            watchdog_message_loop_probe_account=_env(
                raw,
                "WATCHDOG_MESSAGE_LOOP_PROBE_ACCOUNT",
                "default",
            ).strip(),
            watchdog_message_loop_probe_channel=_env(raw, "WATCHDOG_MESSAGE_LOOP_PROBE_CHANNEL", "").strip(),
            watchdog_message_loop_probe_target=_env(raw, "WATCHDOG_MESSAGE_LOOP_PROBE_TARGET", "").strip(),
            watchdog_message_loop_probe_reply_from=_env(raw, "WATCHDOG_MESSAGE_LOOP_PROBE_REPLY_FROM", "").strip(),
            watchdog_message_loop_probe_events_file=_env_path(
                raw,
                "WATCHDOG_MESSAGE_LOOP_PROBE_EVENTS_FILE",
                "~/.openclaw-backup/watchdog/message-loop-probe-events.jsonl",
            ),
            watchdog_message_loop_probe_timeout_seconds=max(1, _env_int(raw, "WATCHDOG_MESSAGE_LOOP_PROBE_TIMEOUT_SECONDS", 20)),
            watchdog_message_loop_probe_cooldown_seconds=max(0, _env_int(raw, "WATCHDOG_MESSAGE_LOOP_PROBE_COOLDOWN_SECONDS", 60)),
            watchdog_doctor_timeout_seconds=_env_int(raw, "WATCHDOG_DOCTOR_TIMEOUT_SECONDS", 45),
            watchdog_enable_doctor_repair=_env_bool(raw, "WATCHDOG_ENABLE_DOCTOR_REPAIR", True),
            watchdog_enable_pre_repair_backup=_env_bool(raw, "WATCHDOG_ENABLE_PRE_REPAIR_BACKUP", False),
            watchdog_backup_script=_env_path(raw, "WATCHDOG_BACKUP_SCRIPT", "./tools/openclaw-backup.js"),
            watchdog_backup_env_file=_env_path(raw, "WATCHDOG_BACKUP_ENV_FILE", "./config/openclaw-backup.env"),
            watchdog_backup_timeout_seconds=_env_int(raw, "WATCHDOG_BACKUP_TIMEOUT_SECONDS", 900),
            watchdog_keep_rollbacks=max(1, _env_int(raw, "WATCHDOG_KEEP_ROLLBACKS", 10)),
            watchdog_last_good_manifest_file=_env_path(raw, "WATCHDOG_LAST_GOOD_MANIFEST_FILE", "~/.openclaw-backup/watchdog/last-good-manifest.json"),
            watchdog_last_good_generations=max(1, _env_int(raw, "WATCHDOG_LAST_GOOD_GENERATIONS", 5)),
            watchdog_guard_manifest_file=_env_path(raw, "WATCHDOG_GUARD_MANIFEST_FILE", "~/.openclaw-backup/watchdog/drift-guard.json"),
            watchdog_protected_paths=_env_csv(raw, "WATCHDOG_PROTECTED_PATHS", ""),
            watchdog_enable_drift_auto_rollback=_env_bool(raw, "WATCHDOG_ENABLE_DRIFT_AUTO_ROLLBACK", True),
            watchdog_keep_incidents=max(1, _env_int(raw, "WATCHDOG_KEEP_INCIDENTS", 10)),
            watchdog_codex_bin=_env(raw, "WATCHDOG_CODEX_BIN", "codex"),
            watchdog_codex_model_hint=_env(raw, "WATCHDOG_CODEX_MODEL_HINT", "gpt-5.4-xhigh"),
            watchdog_codex_workdir=_env_path(raw, "WATCHDOG_CODEX_WORKDIR", "~"),
            watchdog_codex_timeout_seconds=_env_int(raw, "WATCHDOG_CODEX_TIMEOUT_SECONDS", 1800),
            watchdog_claude_code_bin=_env(raw, "WATCHDOG_CLAUDE_CODE_BIN", "claude"),
            watchdog_claude_code_workdir=_env_path(raw, "WATCHDOG_CLAUDE_CODE_WORKDIR", "~"),
            watchdog_claude_code_timeout_seconds=_env_int(raw, "WATCHDOG_CLAUDE_CODE_TIMEOUT_SECONDS", 1800),
            watchdog_gemini_cli_bin=_env(raw, "WATCHDOG_GEMINI_CLI_BIN", "gemini"),
            watchdog_gemini_cli_workdir=_env_path(raw, "WATCHDOG_GEMINI_CLI_WORKDIR", "~"),
            watchdog_gemini_cli_timeout_seconds=_env_int(raw, "WATCHDOG_GEMINI_CLI_TIMEOUT_SECONDS", 1800),
            watchdog_opencode_bin=_env(raw, "WATCHDOG_OPENCODE_BIN", "opencode"),
            watchdog_opencode_workdir=_env_path(raw, "WATCHDOG_OPENCODE_WORKDIR", "~"),
            watchdog_opencode_timeout_seconds=_env_int(raw, "WATCHDOG_OPENCODE_TIMEOUT_SECONDS", 1800),
            watchdog_litellm_enabled=_env_bool(raw, "WATCHDOG_LITELLM_ENABLED", False),
            watchdog_litellm_model=_env(raw, "WATCHDOG_LITELLM_MODEL", "").strip(),
            watchdog_litellm_api_base=_env(raw, "WATCHDOG_LITELLM_API_BASE", "").strip(),
            watchdog_litellm_api_key_env=_env(raw, "WATCHDOG_LITELLM_API_KEY_ENV", "OPENAI_API_KEY").strip(),
            watchdog_litellm_timeout_seconds=max(1, _env_int(raw, "WATCHDOG_LITELLM_TIMEOUT_SECONDS", 60)),
            watchdog_rescue_knowledge_root=_env_path(raw, "WATCHDOG_RESCUE_KNOWLEDGE_ROOT", "~/.openclaw-backup/watchdog/rescue"),
            watchdog_rescue_cases_dir=_env_path(raw, "WATCHDOG_RESCUE_CASES_DIR", "~/.openclaw-backup/watchdog/rescue/cases"),
            watchdog_rescue_candidate_rules_dir=_env_path(
                raw,
                "WATCHDOG_RESCUE_CANDIDATE_RULES_DIR",
                "~/.openclaw-backup/watchdog/rescue/candidate-rules",
            ),
            watchdog_rescue_rules_dir=_env_path(raw, "WATCHDOG_RESCUE_RULES_DIR", "~/.openclaw-backup/watchdog/rescue/rules"),
            watchdog_rescue_reviews_dir=_env_path(raw, "WATCHDOG_RESCUE_REVIEWS_DIR", "~/.openclaw-backup/watchdog/rescue/reviews"),
            watchdog_rescue_editable_paths=_env_csv(
                raw,
                "WATCHDOG_RESCUE_EDITABLE_PATHS",
                "~/.openclaw/openclaw.json,~/.openclaw-backup/watchdog/openclaw.survival.json",
            ),
            watchdog_rescue_editable_keys=_env_csv(
                raw,
                "WATCHDOG_RESCUE_EDITABLE_KEYS",
                "channels,extensions,mcpServers,services,workers,schedules",
            ),
        )
