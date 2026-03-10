from __future__ import annotations

import json
import os
import shutil
import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from watchdog_v2 import repair as repair_ops
from watchdog_v2.config import Config

QQ_PLUGIN_INSTALL_COMMAND = "openclaw plugins install @sliverp/qqbot@latest"
QQ_PLUGIN_PACKAGE = "@sliverp/qqbot@latest"

OPENCODE_CONFIG_SCHEMA_URL = "https://opencode.ai/config.json"

QQBOT_APP_ID_PLACEHOLDER = "REPLACE_WITH_QQBOT_APP_ID"
QQBOT_CLIENT_SECRET_PLACEHOLDER = "REPLACE_WITH_QQBOT_CLIENT_SECRET"
FEISHU_APP_ID_PLACEHOLDER = "REPLACE_WITH_FEISHU_APP_ID"
FEISHU_APP_SECRET_PLACEHOLDER = "REPLACE_WITH_FEISHU_APP_SECRET"

FEISHU_LOG_MARKERS = [
    "feishu_doc: Registered feishu_doc, feishu_app_scopes",
    "feishu_chat: Registered feishu_chat tool",
    "feishu_wiki: Registered feishu_wiki tool",
    "feishu_drive: Registered feishu_drive tool",
    "feishu_perm: Registered feishu_perm tool",
    "feishu_bitable: Registered bitable tools",
    "[MCP] Plugin registered",
]


@dataclass(frozen=True)
class ShellResult:
    command: str
    returncode: int
    stdout: str
    stderr: str
    timed_out: bool = False

    @property
    def output(self) -> str:
        return f"{self.stdout}{self.stderr}"


@dataclass(frozen=True)
class BootstrapOutcome:
    exit_code: int
    state: str
    summary: str
    payload: dict[str, Any]


class BootstrapError(RuntimeError):
    pass


class Bootstrapper:
    def __init__(self, config: Config, *, allow_install: bool, dry_run: bool):
        self.config = config
        self.allow_install = allow_install
        self.dry_run = dry_run

    def run(self) -> BootstrapOutcome:
        payload: dict[str, Any] = {
            "state": "unknown",
            "summary": "",
            "dry_run": self.dry_run,
            "default_channels": ["qqbot", "feishu"],
            "flow": [
                "ensure-opencode",
                "ensure-opencode-free-model",
                "detect-codex",
                "detect-openclaw",
                "ensure-openclaw-if-confirmed",
                "ensure-qq-plugin",
                "ensure-openclaw-channel-config",
                "scan-feishu-runtime-markers",
            ],
            "opencode": {"config": {}},
            "codex": {},
            "openclaw": {},
            "qq_plugin": {"package": QQ_PLUGIN_PACKAGE, "command": QQ_PLUGIN_INSTALL_COMMAND},
            "config": {"path": str(self.config.openclaw_config)},
            "feishu_runtime": {},
            "next_steps": [],
        }

        opencode_payload = self.ensure_opencode()
        payload["opencode"] = opencode_payload

        codex_payload = self.detect_codex()
        payload["codex"] = codex_payload

        if opencode_payload.get("status") == "failed":
            payload["next_steps"].append("Fix the OpenCode install/config problem and rerun bootstrap.")
            warnings: list[str] = []
            self.add_tooling_warnings(payload, warnings)
            if warnings:
                payload["warnings"] = warnings
            return self.finish(
                payload,
                state="failed",
                summary=opencode_payload.get("summary", "OpenCode bootstrap failed."),
                exit_code=1,
            )

        installed, detected_path, detect_result = self.detect_openclaw()
        payload["openclaw"] = {
            "installed": installed,
            "binary": detected_path,
            "confirmation_required": False,
            "install_allowed": self.allow_install,
            "install_command": self.config.openclaw_install_command,
            "detect_returncode": detect_result.returncode,
        }

        if not installed and not self.allow_install:
            payload["openclaw"]["confirmation_required"] = True
            payload["next_steps"] = [
                "Set OPENCLAW_INSTALL_COMMAND in the env file or shell environment.",
                "Rerun bootstrap with --install-openclaw once you want the install command to execute.",
            ]
            warnings = []
            self.add_tooling_warnings(payload, warnings)
            if warnings:
                payload["warnings"] = warnings
            return self.finish(
                payload,
                state="confirmation-required",
                summary=self.openclaw_confirmation_summary(opencode_payload),
                exit_code=10,
            )

        install_details = self.ensure_openclaw(installed)
        payload["openclaw"].update(install_details)
        effective_openclaw = bool(payload["openclaw"].get("installed", False) or payload["openclaw"].get("would_install", False))
        if not effective_openclaw:
            payload["next_steps"].append("Fix the OpenClaw installation issue and rerun bootstrap.")
            warnings = []
            self.add_tooling_warnings(payload, warnings)
            if warnings:
                payload["warnings"] = warnings
            return self.finish(
                payload,
                state="failed",
                summary=payload["openclaw"].get("summary", "OpenClaw installation failed."),
                exit_code=1,
            )

        qq_payload = self.ensure_qq_plugin()
        payload["qq_plugin"].update(qq_payload)

        config_payload = self.ensure_default_channel_config()
        payload["config"].update(config_payload)

        feishu_payload = self.detect_feishu_runtime_markers()
        payload["feishu_runtime"] = feishu_payload

        disabled_channels = [
            name
            for name, details in payload["config"].get("channels", {}).items()
            if isinstance(details, dict) and not details.get("enabled", False)
        ]
        if disabled_channels:
            payload["config"]["disabled_channels"] = disabled_channels

        failures: list[str] = []
        if payload["qq_plugin"].get("status") == "failed":
            failures.append("QQ plugin install failed")
        if payload["config"].get("status") == "failed":
            failures.append("config scaffold failed")

        warnings: list[str] = []
        self.add_tooling_warnings(payload, warnings)

        if payload["config"].get("placeholders_remaining"):
            warnings.append("fill placeholder credentials before enabling live traffic")
            payload["next_steps"].append(
                "Fill the placeholder credentials, review enabled flags for qqbot/feishu, then restart the gateway manually."
            )
        elif disabled_channels:
            warnings.append(f"review enabled flags for: {', '.join(disabled_channels)}")
            payload["next_steps"].append(
                f"Review and enable these channels if desired: {', '.join(disabled_channels)}, then restart the gateway manually."
            )
        else:
            payload["next_steps"].append("Restart the OpenClaw gateway manually so plugin and channel changes are picked up.")

        if payload["feishu_runtime"].get("checked") and not payload["feishu_runtime"].get("found"):
            warnings.append("Feishu runtime markers were not observed in logs yet")

        changed = any(
            [
                bool(payload["opencode"].get("changed")),
                bool(payload["openclaw"].get("changed")),
                bool(payload["qq_plugin"].get("changed")),
                bool(payload["config"].get("changed")),
            ]
        )

        if failures:
            state = "failed"
            summary = "; ".join(failures)
            exit_code = 1
        elif self.dry_run:
            state = "dry-run"
            summary = "Bootstrap dry-run completed for OpenCode fallback, Codex detection, OpenClaw provisioning, QQ plugin handling, and default channel scaffolding."
            exit_code = 0
        elif changed:
            state = "bootstrapped"
            summary = (
                "Bootstrap completed with OpenCode fallback provisioning, Codex detection, OpenClaw provisioning checks, "
                "QQ plugin handling, and default channel scaffolding."
            )
            exit_code = 0
        else:
            state = "already-ready"
            summary = "OpenCode fallback, QQ plugin, and default channel scaffolding are already in place; Codex availability has been reported."
            exit_code = 0

        if warnings:
            payload["warnings"] = warnings
        return self.finish(payload, state=state, summary=summary, exit_code=exit_code)

    def finish(self, payload: dict[str, Any], *, state: str, summary: str, exit_code: int) -> BootstrapOutcome:
        payload["state"] = state
        payload["summary"] = summary
        payload["exit_code"] = exit_code
        payload["files_changed"] = self.collect_changed_files(payload)
        payload["backup_files"] = self.collect_backup_files(payload)
        return BootstrapOutcome(exit_code=exit_code, state=state, summary=summary, payload=payload)

    def collect_changed_files(self, payload: dict[str, Any]) -> list[str]:
        files: list[str] = []
        opencode_config = payload.get("opencode", {}).get("config", {})
        if opencode_config.get("changed"):
            files.append(opencode_config.get("path", ""))
        openclaw_config = payload.get("config", {})
        if openclaw_config.get("changed"):
            files.append(openclaw_config.get("path", ""))
        return self.unique_nonempty(files)

    def collect_backup_files(self, payload: dict[str, Any]) -> list[str]:
        backups = [
            payload.get("opencode", {}).get("config", {}).get("backup_path", ""),
            payload.get("config", {}).get("backup_path", ""),
        ]
        return self.unique_nonempty(backups)

    def unique_nonempty(self, values: list[str]) -> list[str]:
        seen: set[str] = set()
        ordered: list[str] = []
        for value in values:
            if not value or value in seen:
                continue
            seen.add(value)
            ordered.append(value)
        return ordered

    def add_tooling_warnings(self, payload: dict[str, Any], warnings: list[str]) -> None:
        opencode = payload.get("opencode", {})
        codex = payload.get("codex", {})

        if opencode and not opencode.get("watchdog_bin_available", False):
            watchdog_bin = opencode.get("watchdog_bin") or self.config.watchdog_opencode_fallback_bin
            detected_binary = opencode.get("binary") or "opencode"
            warnings.append(f"WATCHDOG_OPENCODE_FALLBACK_BIN does not currently resolve: {watchdog_bin}")
            payload["next_steps"].append(
                f"Update WATCHDOG_OPENCODE_FALLBACK_BIN if needed so watchdog autorun can find OpenCode ({detected_binary})."
            )

        if codex and not codex.get("available", False):
            warnings.append("Codex was not detected; OpenCode remains the prepared fallback path")
            payload["next_steps"].append("Install Codex separately later if you want a primary autorun path in addition to OpenCode.")
        elif codex and not codex.get("configured_available", False) and codex.get("detected_binary"):
            warnings.append("Codex was detected on PATH but WATCHDOG_CODEX_BIN does not currently resolve")
            payload["next_steps"].append(
                "Update WATCHDOG_CODEX_BIN if you want watchdog autorun to use the detected Codex binary."
            )

    def openclaw_confirmation_summary(self, opencode_payload: dict[str, Any]) -> str:
        summary = "OpenClaw is not installed; rerun with --install-openclaw after setting OPENCLAW_INSTALL_COMMAND."
        if self.dry_run and (opencode_payload.get("would_install") or opencode_payload.get("config", {}).get("changed")):
            return f"{summary} OpenCode fallback changes are planned by dry-run."
        if opencode_payload.get("status") in {"ready", "planned"}:
            return f"{summary} OpenCode fallback is ready."
        return summary

    def run_shell(self, command: str, *, timeout: int | None = None) -> ShellResult:
        try:
            completed = subprocess.run(
                ["/bin/bash", "-c", command],
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=timeout,
                check=False,
            )
            return ShellResult(
                command=command,
                returncode=completed.returncode,
                stdout=completed.stdout or "",
                stderr=completed.stderr or "",
            )
        except subprocess.TimeoutExpired as exc:
            return ShellResult(
                command=command,
                returncode=124,
                stdout=exc.stdout or "",
                stderr=exc.stderr or f"timed out after {timeout}s",
                timed_out=True,
            )

    def detect_binary(self, candidate: str) -> tuple[bool, str, ShellResult]:
        candidate = candidate.strip()
        if not candidate:
            return False, "", ShellResult(command="", returncode=1, stdout="", stderr="empty candidate")
        if "/" in candidate:
            resolved = str(Path(candidate).expanduser())
            available = os.access(resolved, os.X_OK)
            return (
                available,
                resolved if available else "",
                ShellResult(
                    command=f"test -x {resolved}",
                    returncode=0 if available else 1,
                    stdout=f"{resolved}\n" if available else "",
                    stderr="",
                ),
            )
        detected = shutil.which(candidate) or ""
        return (
            bool(detected),
            detected,
            ShellResult(
                command=f"command -v {candidate}",
                returncode=0 if detected else 1,
                stdout=f"{detected}\n" if detected else "",
                stderr="",
            ),
        )

    def detect_openclaw(self) -> tuple[bool, str, ShellResult]:
        return self.detect_binary("openclaw")

    def detect_codex(self) -> dict[str, Any]:
        configured_available, configured_binary, configured_result = self.detect_binary(self.config.watchdog_codex_bin)
        path_available, path_binary, path_result = self.detect_binary("codex")
        detected_binary = configured_binary or path_binary
        return {
            "configured_bin": self.config.watchdog_codex_bin,
            "configured_available": configured_available,
            "configured_binary": configured_binary,
            "configured_detect_returncode": configured_result.returncode,
            "path_available": path_available,
            "path_binary": path_binary,
            "path_detect_returncode": path_result.returncode,
            "available": configured_available or path_available,
            "detected_binary": detected_binary,
        }

    def ensure_opencode(self) -> dict[str, Any]:
        installed, detected_path, detect_result = self.detect_binary("opencode")
        payload: dict[str, Any] = {
            "status": "ready",
            "changed": False,
            "installed": installed,
            "binary": detected_path,
            "install_attempted": False,
            "install_returncode": 0,
            "would_install": False,
            "install_command": self.config.opencode_install_command,
            "desired_model": self.config.opencode_bootstrap_model,
            "detect_returncode": detect_result.returncode,
            "config": {},
            "watchdog_bin": self.config.watchdog_opencode_fallback_bin,
            "watchdog_bin_available": False,
            "watchdog_binary": "",
        }

        effective_installed = installed
        if not installed:
            install_command = self.config.opencode_install_command.strip()
            if not install_command:
                payload["status"] = "failed"
                payload["summary"] = "OpenCode is missing and OPENCODE_INSTALL_COMMAND is empty."
                self.populate_opencode_watchdog_status(payload)
                return payload
            payload["install_attempted"] = True
            if self.dry_run:
                payload["would_install"] = True
                payload["changed"] = True
                effective_installed = True
            else:
                result = self.run_shell(install_command, timeout=self.config.openclaw_bootstrap_timeout_seconds)
                payload["install_returncode"] = result.returncode
                payload["install_stdout"] = result.stdout.strip()
                payload["install_stderr"] = result.stderr.strip()
                detected, detected_path, _ = self.detect_binary("opencode")
                payload["installed"] = detected
                payload["binary"] = detected_path
                payload["changed"] = detected and result.returncode == 0
                effective_installed = detected
                if not detected:
                    payload["status"] = "failed"
                    payload["summary"] = "OpenCode install command finished but opencode is still not on PATH."
                    payload["config"] = {
                        "path": str(self.config.opencode_bootstrap_config_path),
                        "status": "blocked",
                        "changed": False,
                        "backup_path": "",
                        "created": False,
                        "desired_model": self.config.opencode_bootstrap_model,
                        "configured_model": "",
                        "previous_model": "",
                    }
                    self.populate_opencode_watchdog_status(payload)
                    return payload

        config_payload = self.ensure_opencode_config()
        payload["config"] = config_payload
        payload["changed"] = bool(payload["changed"] or config_payload.get("changed"))
        self.populate_opencode_watchdog_status(payload)

        if config_payload.get("status") == "failed":
            payload["status"] = "failed"
            payload["summary"] = config_payload.get("error", "OpenCode config update failed.")
            return payload

        if not effective_installed:
            payload["status"] = "failed"
            payload["summary"] = "OpenCode is still unavailable after bootstrap."
            return payload

        if self.dry_run and (payload.get("would_install") or config_payload.get("changed")):
            payload["status"] = "planned"
            payload["summary"] = "OpenCode install/config changes are planned by dry-run."
            return payload

        if payload["changed"]:
            payload["summary"] = "OpenCode is installed and configured with the desired free fallback model."
        else:
            payload["summary"] = "OpenCode is already installed and configured with the desired free fallback model."
        return payload

    def populate_opencode_watchdog_status(self, payload: dict[str, Any]) -> None:
        watchdog_available, watchdog_binary, _ = self.detect_binary(self.config.watchdog_opencode_fallback_bin)
        payload["watchdog_bin_available"] = watchdog_available
        payload["watchdog_binary"] = watchdog_binary

    def ensure_opencode_config(self) -> dict[str, Any]:
        path = self.config.opencode_bootstrap_config_path.expanduser()
        desired_model = self.config.opencode_bootstrap_model
        exists_before = path.exists()
        payload: dict[str, Any] = {
            "status": "ready",
            "path": str(path),
            "exists_before": exists_before,
            "changed": False,
            "backup_path": "",
            "created": False,
            "desired_model": desired_model,
            "configured_model": "",
            "previous_model": "",
        }

        try:
            current = self.load_json_object(
                path,
                label="existing OpenCode config",
                allow_jsonc=True,
            ) if exists_before else {}
        except BootstrapError as exc:
            payload["status"] = "failed"
            payload["error"] = str(exc)
            return payload

        changed = False
        schema_value = current.get("$schema")
        if schema_value in (None, ""):
            current["$schema"] = OPENCODE_CONFIG_SCHEMA_URL
            changed = True

        previous_model = current.get("model")
        if isinstance(previous_model, str):
            payload["previous_model"] = previous_model
        elif previous_model is not None:
            payload["previous_model"] = json.dumps(previous_model, ensure_ascii=False)

        if current.get("model") != desired_model:
            current["model"] = desired_model
            changed = True

        payload["configured_model"] = str(current.get("model", ""))

        if not changed:
            return payload

        payload["changed"] = True
        payload["created"] = not exists_before
        rendered = json.dumps(current, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        if self.dry_run:
            payload["status"] = "planned"
            if exists_before:
                payload["backup_path"] = str(self.build_backup_path(path))
            return payload

        path.parent.mkdir(parents=True, exist_ok=True)
        guard_before = repair_ops.protected_paths_snapshot(self.config)
        repair_ops.record_guard_event(
            self.config,
            operation="bootstrap-opencode-config",
            phase="before",
            before=guard_before,
            context={"path": str(path), "changed": True, "desired_model": desired_model},
        )
        if exists_before:
            backup_path = self.build_backup_path(path)
            shutil.copy2(path, backup_path)
            payload["backup_path"] = str(backup_path)
        path.write_text(rendered, encoding="utf-8")
        guard_after = repair_ops.protected_paths_snapshot(self.config)
        payload["guard"] = repair_ops.record_guard_event(
            self.config,
            operation="bootstrap-opencode-config",
            phase="after",
            before=guard_before,
            after=guard_after,
            validation="json-valid",
            context={"path": str(path), "backup_path": payload.get("backup_path", ""), "desired_model": desired_model},
        )
        return payload

    def load_json_object(self, path: Path, *, label: str, allow_jsonc: bool) -> dict[str, Any]:
        try:
            text = path.read_text(encoding="utf-8")
        except OSError as exc:
            raise BootstrapError(f"failed to read {label}: {exc}") from exc
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError as exc:
            if not allow_jsonc:
                raise BootstrapError(f"{label} is not valid JSON: {exc}") from exc
            normalized = self.normalize_jsonc(text)
            try:
                parsed = json.loads(normalized)
            except json.JSONDecodeError as inner_exc:
                raise BootstrapError(f"{label} is not valid JSON/JSONC: {inner_exc}") from inner_exc
        if not isinstance(parsed, dict):
            raise BootstrapError(f"{label} must be a JSON object")
        return parsed

    def normalize_jsonc(self, text: str) -> str:
        return self.strip_trailing_commas(self.strip_jsonc_comments(text))

    def strip_jsonc_comments(self, text: str) -> str:
        output: list[str] = []
        in_string = False
        escaping = False
        in_line_comment = False
        in_block_comment = False
        index = 0
        while index < len(text):
            char = text[index]
            next_char = text[index + 1] if index + 1 < len(text) else ""

            if in_line_comment:
                if char in "\r\n":
                    in_line_comment = False
                    output.append(char)
                index += 1
                continue

            if in_block_comment:
                if char == "*" and next_char == "/":
                    in_block_comment = False
                    index += 2
                    continue
                if char in "\r\n":
                    output.append(char)
                index += 1
                continue

            if in_string:
                output.append(char)
                if escaping:
                    escaping = False
                elif char == "\\":
                    escaping = True
                elif char == '"':
                    in_string = False
                index += 1
                continue

            if char == '"':
                in_string = True
                output.append(char)
                index += 1
                continue

            if char == "/" and next_char == "/":
                in_line_comment = True
                index += 2
                continue

            if char == "/" and next_char == "*":
                in_block_comment = True
                index += 2
                continue

            output.append(char)
            index += 1

        return "".join(output)

    def strip_trailing_commas(self, text: str) -> str:
        output: list[str] = []
        in_string = False
        escaping = False
        index = 0
        while index < len(text):
            char = text[index]
            if in_string:
                output.append(char)
                if escaping:
                    escaping = False
                elif char == "\\":
                    escaping = True
                elif char == '"':
                    in_string = False
                index += 1
                continue

            if char == '"':
                in_string = True
                output.append(char)
                index += 1
                continue

            if char == ",":
                lookahead = index + 1
                while lookahead < len(text) and text[lookahead] in " \t\r\n":
                    lookahead += 1
                if lookahead < len(text) and text[lookahead] in "]}":
                    index += 1
                    continue

            output.append(char)
            index += 1

        return "".join(output)

    def ensure_openclaw(self, installed: bool) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "changed": False,
            "install_attempted": False,
            "install_returncode": 0,
            "would_install": False,
        }
        if installed:
            payload["summary"] = "OpenClaw already installed."
            return payload
        install_command = self.config.openclaw_install_command.strip()
        if not install_command:
            payload["summary"] = "OpenClaw is missing and OPENCLAW_INSTALL_COMMAND is not configured."
            payload["install_returncode"] = 2
            return payload
        payload["install_attempted"] = True
        payload["install_command"] = install_command
        if self.dry_run:
            payload["would_install"] = True
            payload["changed"] = True
            payload["summary"] = "OpenClaw install is planned by dry-run."
            return payload
        result = self.run_shell(install_command, timeout=self.config.openclaw_bootstrap_timeout_seconds)
        payload["install_returncode"] = result.returncode
        payload["install_stdout"] = result.stdout.strip()
        payload["install_stderr"] = result.stderr.strip()
        detected, detected_path, _ = self.detect_openclaw()
        payload["installed"] = detected
        payload["binary"] = detected_path
        payload["changed"] = detected and result.returncode == 0
        payload["summary"] = "OpenClaw install command completed successfully." if detected else "OpenClaw install command finished but openclaw is still not on PATH."
        return payload

    def ensure_qq_plugin(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "status": "ready",
            "changed": False,
            "installed": False,
            "install_attempted": False,
            "install_returncode": 0,
        }
        list_result = self.run_shell("openclaw plugins list", timeout=60)
        output = list_result.output.lower()
        installed = list_result.returncode == 0 and ("@sliverp/qqbot" in output or "qqbot" in output)
        payload["detect_returncode"] = list_result.returncode
        payload["detect_output"] = list_result.output.strip()
        payload["installed"] = installed
        if installed:
            return payload
        payload["status"] = "installing"
        payload["install_attempted"] = True
        if self.dry_run:
            payload["changed"] = True
            payload["status"] = "planned"
            payload["would_install"] = True
            return payload
        result = self.run_shell(QQ_PLUGIN_INSTALL_COMMAND, timeout=self.config.openclaw_bootstrap_timeout_seconds)
        payload["install_returncode"] = result.returncode
        payload["install_stdout"] = result.stdout.strip()
        payload["install_stderr"] = result.stderr.strip()
        verify_result = self.run_shell("openclaw plugins list", timeout=60)
        verify_output = verify_result.output.lower()
        payload["installed"] = verify_result.returncode == 0 and ("@sliverp/qqbot" in verify_output or "qqbot" in verify_output)
        payload["verify_returncode"] = verify_result.returncode
        payload["changed"] = payload["installed"] and result.returncode == 0
        payload["status"] = "ready" if payload["installed"] else "failed"
        return payload

    def ensure_default_channel_config(self) -> dict[str, Any]:
        path = self.config.openclaw_config
        exists_before = path.exists()
        payload: dict[str, Any] = {
            "status": "ready",
            "path": str(path),
            "exists_before": exists_before,
            "changed": False,
            "backup_path": "",
            "created": False,
            "placeholders_remaining": [],
            "channels": {},
        }

        if exists_before:
            try:
                current = self.load_json_object(path, label="existing OpenClaw config", allow_jsonc=False)
            except BootstrapError as exc:
                payload["status"] = "failed"
                payload["error"] = str(exc)
                return payload
        else:
            current = {}

        try:
            changed = False
            channels, channels_changed = self.ensure_mapping(current, "channels", "channels")
            changed = changed or channels_changed

            qq_payload, qq_changed = self.merge_qqbot(channels)
            feishu_payload, feishu_changed = self.merge_feishu(channels)
            changed = changed or qq_changed or feishu_changed
        except BootstrapError as exc:
            payload["status"] = "failed"
            payload["error"] = str(exc)
            return payload

        payload["channels"] = {"qqbot": qq_payload, "feishu": feishu_payload}
        placeholders = qq_payload["placeholders_remaining"] + feishu_payload["placeholders_remaining"]
        payload["placeholders_remaining"] = placeholders

        if not changed:
            return payload

        payload["changed"] = True
        payload["created"] = not exists_before
        rendered = json.dumps(current, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        if self.dry_run:
            payload["status"] = "planned"
            if exists_before:
                payload["backup_path"] = str(self.build_backup_path(path))
            return payload

        path.parent.mkdir(parents=True, exist_ok=True)
        guard_before = repair_ops.protected_paths_snapshot(self.config)
        repair_ops.record_guard_event(
            self.config,
            operation="bootstrap-openclaw-config",
            phase="before",
            before=guard_before,
            context={
                "path": str(path),
                "changed": True,
                "required_channels": list(payload["channels"].keys()),
                "placeholders_remaining": list(placeholders),
            },
        )
        if exists_before:
            backup_path = self.build_backup_path(path)
            shutil.copy2(path, backup_path)
            payload["backup_path"] = str(backup_path)
        path.write_text(rendered, encoding="utf-8")
        guard_after = repair_ops.protected_paths_snapshot(self.config)
        payload["guard"] = repair_ops.record_guard_event(
            self.config,
            operation="bootstrap-openclaw-config",
            phase="after",
            before=guard_before,
            after=guard_after,
            validation="json-valid",
            context={
                "path": str(path),
                "backup_path": payload.get("backup_path", ""),
                "required_channels": list(payload["channels"].keys()),
                "placeholders_remaining": list(placeholders),
            },
        )
        return payload

    def merge_qqbot(self, channels: dict[str, Any]) -> tuple[dict[str, Any], bool]:
        qqbot, changed = self.ensure_mapping(channels, "qqbot", "channels.qqbot")
        supplied_app_id = self.config.openclaw_bootstrap_qqbot_app_id
        supplied_client_secret = self.config.openclaw_bootstrap_qqbot_client_secret
        changed = self.ensure_placeholder_or_value(qqbot, "appId", supplied_app_id, QQBOT_APP_ID_PLACEHOLDER) or changed
        changed = self.ensure_placeholder_or_value(qqbot, "clientSecret", supplied_client_secret, QQBOT_CLIENT_SECRET_PLACEHOLDER) or changed
        if "enabled" not in qqbot:
            qqbot["enabled"] = bool(supplied_app_id and supplied_client_secret)
            changed = True
        placeholders_remaining = []
        if qqbot.get("appId") == QQBOT_APP_ID_PLACEHOLDER:
            placeholders_remaining.append("channels.qqbot.appId")
        if qqbot.get("clientSecret") == QQBOT_CLIENT_SECRET_PLACEHOLDER:
            placeholders_remaining.append("channels.qqbot.clientSecret")
        return {
            "path": "channels.qqbot",
            "enabled": bool(qqbot.get("enabled")),
            "placeholders_remaining": placeholders_remaining,
        }, changed

    def merge_feishu(self, channels: dict[str, Any]) -> tuple[dict[str, Any], bool]:
        feishu, changed = self.ensure_mapping(channels, "feishu", "channels.feishu")
        use_top_level = any(key in feishu for key in ("appId", "appSecret"))
        target = feishu
        credential_path = "channels.feishu"
        if not use_top_level:
            accounts, nested_changed = self.ensure_mapping(feishu, "accounts", "channels.feishu.accounts")
            main, main_changed = self.ensure_mapping(accounts, "main", "channels.feishu.accounts.main")
            target = main
            credential_path = "channels.feishu.accounts.main"
            changed = changed or nested_changed or main_changed
            if "defaultAccount" not in feishu:
                feishu["defaultAccount"] = "main"
                changed = True
        supplied_app_id = self.config.openclaw_bootstrap_feishu_app_id
        supplied_app_secret = self.config.openclaw_bootstrap_feishu_app_secret
        changed = self.ensure_placeholder_or_value(target, "appId", supplied_app_id, FEISHU_APP_ID_PLACEHOLDER) or changed
        changed = self.ensure_placeholder_or_value(target, "appSecret", supplied_app_secret, FEISHU_APP_SECRET_PLACEHOLDER) or changed
        if credential_path.endswith("main") and "botName" not in target and self.config.openclaw_bootstrap_feishu_bot_name:
            target["botName"] = self.config.openclaw_bootstrap_feishu_bot_name
            changed = True
        if "enabled" not in feishu:
            feishu["enabled"] = bool(supplied_app_id and supplied_app_secret)
            changed = True
        placeholders_remaining = []
        if target.get("appId") == FEISHU_APP_ID_PLACEHOLDER:
            placeholders_remaining.append(f"{credential_path}.appId")
        if target.get("appSecret") == FEISHU_APP_SECRET_PLACEHOLDER:
            placeholders_remaining.append(f"{credential_path}.appSecret")
        return {
            "path": credential_path,
            "enabled": bool(feishu.get("enabled")),
            "placeholders_remaining": placeholders_remaining,
        }, changed

    def ensure_mapping(self, parent: dict[str, Any], key: str, path: str) -> tuple[dict[str, Any], bool]:
        current = parent.get(key)
        if current is None:
            parent[key] = {}
            return parent[key], True
        if not isinstance(current, dict):
            raise BootstrapError(f"{path} must be a JSON object")
        return current, False

    def ensure_placeholder_or_value(self, target: dict[str, Any], key: str, supplied: str, placeholder: str) -> bool:
        current = target.get(key)
        desired = supplied or placeholder
        if current in (None, "", placeholder) and current != desired:
            target[key] = desired
            return True
        if current is None:
            target[key] = desired
            return True
        return False

    def build_backup_path(self, path: Path) -> Path:
        timestamp = datetime.now().astimezone().strftime("%Y%m%d-%H%M%S-%f")
        return path.with_name(f"{path.name}.bak.{timestamp}")

    def detect_feishu_runtime_markers(self) -> dict[str, Any]:
        candidates = self.log_candidates()
        payload: dict[str, Any] = {
            "checked": False,
            "found": False,
            "log_file": "",
            "matched_markers": [],
        }
        for candidate in candidates:
            if not candidate.exists() or not candidate.is_file():
                continue
            payload["checked"] = True
            payload["log_file"] = str(candidate)
            text = self.read_tail(candidate)
            matched = [marker for marker in FEISHU_LOG_MARKERS if marker in text]
            if matched:
                payload["found"] = True
                payload["matched_markers"] = matched
                return payload
        return payload

    def log_candidates(self) -> list[Path]:
        candidates: list[Path] = []
        if self.config.openclaw_bootstrap_log_file is not None:
            candidates.append(self.config.openclaw_bootstrap_log_file)
        config_log = self.read_logging_file_from_config()
        if config_log is not None:
            candidates.append(config_log)
        default_dir = Path("/tmp/openclaw")
        if default_dir.exists():
            candidates.extend(sorted(default_dir.glob("openclaw-*.log"), reverse=True)[:3])
        seen: set[Path] = set()
        ordered: list[Path] = []
        for candidate in candidates:
            resolved = candidate.expanduser()
            if resolved not in seen:
                seen.add(resolved)
                ordered.append(resolved)
        return ordered

    def read_logging_file_from_config(self) -> Path | None:
        if not self.config.openclaw_config.exists():
            return None
        try:
            current = self.load_json_object(self.config.openclaw_config, label="existing OpenClaw config", allow_jsonc=False)
        except BootstrapError:
            return None
        logging = current.get("logging")
        if not isinstance(logging, dict):
            return None
        file_value = logging.get("file")
        if not isinstance(file_value, str) or not file_value.strip():
            return None
        return Path(file_value).expanduser()

    def read_tail(self, path: Path, max_bytes: int = 262144) -> str:
        with path.open("rb") as handle:
            handle.seek(0, 2)
            size = handle.tell()
            handle.seek(max(0, size - max_bytes))
            return handle.read().decode("utf-8", errors="replace")
