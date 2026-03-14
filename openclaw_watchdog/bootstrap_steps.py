from __future__ import annotations

from dataclasses import dataclass

from openclaw_watchdog.models import BootstrapSummary


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



def _record_executor(summary: BootstrapSummary, name: str, payload: dict[str, object]) -> None:
    summary.executors[name] = dict(payload)



def detect_opencode_step(bootstrapper, summary: BootstrapSummary) -> PipelineResult:
    summary.opencode = bootstrapper.detect_opencode()
    _record_executor(summary, 'opencode', summary.opencode)
    return _continue(summary)



def detect_codex_step(bootstrapper, summary: BootstrapSummary) -> PipelineResult:
    summary.codex = bootstrapper.detect_codex()
    _record_executor(summary, 'codex', summary.codex)
    return _continue(summary)



def detect_claude_code_step(bootstrapper, summary: BootstrapSummary) -> PipelineResult:
    _record_executor(summary, 'claude-code', bootstrapper.detect_claude_code())
    return _continue(summary)



def detect_gemini_cli_step(bootstrapper, summary: BootstrapSummary) -> PipelineResult:
    _record_executor(summary, 'gemini-cli', bootstrapper.detect_gemini_cli())
    return _continue(summary)



def detect_litellm_step(bootstrapper, summary: BootstrapSummary) -> PipelineResult:
    _record_executor(summary, 'litellm', bootstrapper.detect_litellm())
    return _continue(summary)



def detect_openclaw_step(bootstrapper, summary: BootstrapSummary) -> PipelineResult:
    summary.openclaw = bootstrapper.detect_openclaw()
    if not bool(summary.openclaw.get('available', False)):
        summary.next_steps.append('Install or expose OpenClaw on PATH before enabling live rescue flows.')
    return _continue(summary)



def inspect_qq_plugin_step(bootstrapper, summary: BootstrapSummary) -> PipelineResult:
    summary.qq_plugin.update(bootstrapper.inspect_qq_plugin())
    return _continue(summary)



def inspect_default_channel_config_step(bootstrapper, summary: BootstrapSummary) -> PipelineResult:
    summary.config.update(bootstrapper.inspect_default_channel_config())
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

    warnings: list[str] = []
    if not bool(summary.openclaw.get('available', False)):
        warnings.append('OpenClaw binary was not detected yet')
    if not bool(summary.qq_plugin.get('installed', False)):
        warnings.append('QQ plugin is not installed yet')
        summary.next_steps.append('Install the QQ plugin manually before expecting qqbot recovery.')
    if summary.config.get('status') == 'missing':
        warnings.append('OpenClaw default channel config is not present yet')
        summary.next_steps.append('Review or create the OpenClaw channel config before enabling live rescue flows.')
    elif summary.config.get('status') == 'failed':
        warnings.append('OpenClaw default channel config could not be inspected')
        summary.next_steps.append('Fix the OpenClaw config file so bootstrap can inspect channel prerequisites.')

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

    if summary.feishu_runtime.get('checked') and not summary.feishu_runtime.get('found'):
        warnings.append('Feishu runtime markers were not observed in logs yet')

    for executor_name, label in (
        ('codex', 'Codex'),
        ('claude-code', 'Claude Code'),
        ('gemini-cli', 'Gemini CLI'),
        ('opencode', 'OpenCode'),
    ):
        payload = summary.executors.get(executor_name, {})
        if isinstance(payload, dict) and not bool(payload.get('available', False)):
            warnings.append(f'{label} was not detected in the rescue chain inventory')

    litellm = summary.executors.get('litellm', {}) if isinstance(summary.executors.get('litellm', {}), dict) else {}
    if litellm and not bool(litellm.get('available', False)):
        warnings.append('LiteLLM specialist agent is not configured yet')

    if summary.opencode and not bool(summary.opencode.get('watchdog_bin_available', False)):
        watchdog_bin = summary.opencode.get('watchdog_bin') or bootstrapper.config.watchdog_opencode_bin
        warnings.append(f'WATCHDOG_OPENCODE_BIN does not currently resolve: {watchdog_bin}')
        summary.next_steps.append(
            f'Update WATCHDOG_OPENCODE_BIN if needed so the rescue chain can find OpenCode ({summary.opencode.get("detected_binary") or "opencode"}).'
        )

    summary.next_steps = bootstrapper.unique_nonempty(summary.next_steps)
    summary.warnings = bootstrapper.unique_nonempty(warnings)

    state = 'attention' if summary.warnings else 'ready'
    message = (
        'Bootstrap readiness inspection found follow-up items for the rescue chain or OpenClaw prerequisites.'
        if state == 'attention'
        else 'Bootstrap readiness inspection completed with the current rescue-chain inventory.'
    )
    return _stop(
        summary,
        state=state,
        message=message,
        exit_code=0,
    )


BOOTSTRAP_STEPS = [
    detect_opencode_step,
    detect_codex_step,
    detect_claude_code_step,
    detect_gemini_cli_step,
    detect_litellm_step,
    detect_openclaw_step,
    inspect_qq_plugin_step,
    inspect_default_channel_config_step,
    detect_feishu_runtime_step,
]



def run_bootstrap_pipeline(bootstrapper, summary: BootstrapSummary) -> PipelineResult:
    result = _continue(summary)
    for step in BOOTSTRAP_STEPS:
        result = step(bootstrapper, result.bootstrap_summary)
        if result.stop:
            return result
    return finalize_bootstrap(bootstrapper, result.bootstrap_summary)
