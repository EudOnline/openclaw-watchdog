from __future__ import annotations

from dataclasses import dataclass

from watchdog_v2.models import BootstrapSummary


@dataclass
class PipelineResult:
    bootstrap_summary: BootstrapSummary
    state: str = ''
    message: str = ''
    exit_code: int = 0

    @property
    def stop(self) -> bool:
        return bool(self.state)


def _continue(summary: BootstrapSummary) -> PipelineResult:
    return PipelineResult(bootstrap_summary=summary)


def _stop(summary: BootstrapSummary, *, state: str, message: str, exit_code: int) -> PipelineResult:
    return PipelineResult(bootstrap_summary=summary, state=state, message=message, exit_code=exit_code)


def _add_tooling_warnings(bootstrapper, summary: BootstrapSummary, warnings: list[str]) -> None:
    opencode = summary.opencode
    codex = summary.codex

    if opencode and not opencode.get('watchdog_bin_available', False):
        watchdog_bin = opencode.get('watchdog_bin') or bootstrapper.config.watchdog_opencode_fallback_bin
        detected_binary = opencode.get('binary') or 'opencode'
        warnings.append(f'WATCHDOG_OPENCODE_FALLBACK_BIN does not currently resolve: {watchdog_bin}')
        summary.next_steps.append(
            f'Update WATCHDOG_OPENCODE_FALLBACK_BIN if needed so watchdog autorun can find OpenCode ({detected_binary}).'
        )

    if codex and not codex.get('available', False):
        warnings.append('Codex was not detected; OpenCode remains the prepared fallback path')
        summary.next_steps.append('Install Codex separately later if you want a primary autorun path in addition to OpenCode.')
    elif codex and not codex.get('configured_available', False) and codex.get('detected_binary'):
        warnings.append('Codex was detected on PATH but WATCHDOG_CODEX_BIN does not currently resolve')
        summary.next_steps.append('Update WATCHDOG_CODEX_BIN if you want watchdog autorun to use the detected Codex binary.')


def ensure_opencode_step(bootstrapper, summary: BootstrapSummary) -> PipelineResult:
    summary.opencode = bootstrapper.ensure_opencode()
    if summary.opencode.get('status') != 'failed':
        return _continue(summary)
    summary.next_steps.append('Fix the OpenCode install/config problem and rerun bootstrap.')
    warnings: list[str] = []
    _add_tooling_warnings(bootstrapper, summary, warnings)
    summary.warnings = bootstrapper.unique_nonempty(warnings)
    return _stop(
        summary,
        state='failed',
        message=str(summary.opencode.get('summary', 'OpenCode bootstrap failed.')),
        exit_code=1,
    )


def detect_codex_step(bootstrapper, summary: BootstrapSummary) -> PipelineResult:
    summary.codex = bootstrapper.detect_codex()
    return _continue(summary)


def detect_openclaw_step(bootstrapper, summary: BootstrapSummary) -> PipelineResult:
    installed, detected_path, detect_result = bootstrapper.detect_openclaw()
    summary.openclaw = {
        'installed': installed,
        'binary': detected_path,
        'confirmation_required': False,
        'install_allowed': bootstrapper.allow_install,
        'install_command': bootstrapper.config.openclaw_install_command,
        'detect_returncode': detect_result.returncode,
    }
    if installed or bootstrapper.allow_install:
        return _continue(summary)
    summary.openclaw['confirmation_required'] = True
    summary.next_steps = [
        'Set OPENCLAW_INSTALL_COMMAND in the env file or shell environment.',
        'Rerun bootstrap with --install-openclaw once you want the install command to execute.',
    ]
    warnings: list[str] = []
    _add_tooling_warnings(bootstrapper, summary, warnings)
    summary.warnings = bootstrapper.unique_nonempty(warnings)
    return _stop(
        summary,
        state='confirmation-required',
        message=bootstrapper.openclaw_confirmation_summary(summary.opencode),
        exit_code=10,
    )


def ensure_openclaw_step(bootstrapper, summary: BootstrapSummary) -> PipelineResult:
    install_details = bootstrapper.ensure_openclaw(bool(summary.openclaw.get('installed', False)))
    summary.openclaw.update(install_details)
    effective_openclaw = bool(summary.openclaw.get('installed', False) or summary.openclaw.get('would_install', False))
    if effective_openclaw:
        return _continue(summary)
    summary.next_steps.append('Fix the OpenClaw installation issue and rerun bootstrap.')
    warnings: list[str] = []
    _add_tooling_warnings(bootstrapper, summary, warnings)
    summary.warnings = bootstrapper.unique_nonempty(warnings)
    return _stop(
        summary,
        state='failed',
        message=str(summary.openclaw.get('summary', 'OpenClaw installation failed.')),
        exit_code=1,
    )


def ensure_qq_plugin_step(bootstrapper, summary: BootstrapSummary) -> PipelineResult:
    summary.qq_plugin.update(bootstrapper.ensure_qq_plugin())
    return _continue(summary)


def ensure_default_channel_config_step(bootstrapper, summary: BootstrapSummary) -> PipelineResult:
    summary.config.update(bootstrapper.ensure_default_channel_config())
    return _continue(summary)


def detect_feishu_runtime_step(bootstrapper, summary: BootstrapSummary) -> PipelineResult:
    summary.feishu_runtime = bootstrapper.detect_feishu_runtime_markers()
    return _continue(summary)


def finalize_bootstrap(bootstrapper, summary: BootstrapSummary) -> PipelineResult:
    channels = summary.config.get('channels', {}) if isinstance(summary.config.get('channels', {}), dict) else {}
    disabled_channels = [
        name
        for name, details in channels.items()
        if isinstance(details, dict) and not details.get('enabled', False)
    ]
    if disabled_channels:
        summary.config['disabled_channels'] = disabled_channels

    failures: list[str] = []
    if summary.qq_plugin.get('status') == 'failed':
        failures.append('QQ plugin install failed')
    if summary.config.get('status') == 'failed':
        failures.append('config scaffold failed')

    warnings: list[str] = []
    _add_tooling_warnings(bootstrapper, summary, warnings)

    placeholders = summary.config.get('placeholders_remaining')
    if placeholders:
        warnings.append('fill placeholder credentials before enabling live traffic')
        summary.next_steps.append(
            'Fill the placeholder credentials, review enabled flags for qqbot/feishu, then restart the gateway manually.'
        )
    elif disabled_channels:
        warnings.append(f"review enabled flags for: {', '.join(disabled_channels)}")
        summary.next_steps.append(
            f"Review and enable these channels if desired: {', '.join(disabled_channels)}, then restart the gateway manually."
        )
    else:
        summary.next_steps.append('Restart the OpenClaw gateway manually so plugin and channel changes are picked up.')

    if summary.feishu_runtime.get('checked') and not summary.feishu_runtime.get('found'):
        warnings.append('Feishu runtime markers were not observed in logs yet')

    summary.next_steps = bootstrapper.unique_nonempty(summary.next_steps)
    summary.warnings = bootstrapper.unique_nonempty(warnings)

    changed = any(
        [
            bool(summary.opencode.get('changed')),
            bool(summary.openclaw.get('changed')),
            bool(summary.qq_plugin.get('changed')),
            bool(summary.config.get('changed')),
        ]
    )

    if failures:
        return _stop(summary, state='failed', message='; '.join(failures), exit_code=1)
    if bootstrapper.dry_run:
        return _stop(
            summary,
            state='dry-run',
            message='Bootstrap dry-run completed for OpenCode fallback, Codex detection, OpenClaw provisioning, QQ plugin handling, and default channel scaffolding.',
            exit_code=0,
        )
    if changed:
        return _stop(
            summary,
            state='bootstrapped',
            message='Bootstrap completed with OpenCode fallback provisioning, Codex detection, OpenClaw provisioning checks, QQ plugin handling, and default channel scaffolding.',
            exit_code=0,
        )
    return _stop(
        summary,
        state='already-ready',
        message='OpenCode fallback, QQ plugin, and default channel scaffolding are already in place; Codex availability has been reported.',
        exit_code=0,
    )


BOOTSTRAP_STEPS = [
    ensure_opencode_step,
    detect_codex_step,
    detect_openclaw_step,
    ensure_openclaw_step,
    ensure_qq_plugin_step,
    ensure_default_channel_config_step,
    detect_feishu_runtime_step,
]


def run_bootstrap_pipeline(bootstrapper, summary: BootstrapSummary) -> PipelineResult:
    result = _continue(summary)
    for step in BOOTSTRAP_STEPS:
        result = step(bootstrapper, result.bootstrap_summary)
        if result.stop:
            return result
    return finalize_bootstrap(bootstrapper, result.bootstrap_summary)
