from pathlib import Path

from watchdog_v2.rescue_agents.base import Runner, StructuredCliAdapter


class ClaudeCodeAdapter(StructuredCliAdapter):
    def __init__(
        self,
        *,
        available: bool = False,
        command: str = 'claude',
        runner: Runner | None = None,
        timeout_seconds: int = 120,
        cwd: Path | None = None,
    ) -> None:
        super().__init__(
            name='claude-code',
            command=command,
            prompt_args=('-p',),
            available=available,
            runner=runner,
            timeout_seconds=timeout_seconds,
            cwd=cwd,
            provider_label='Claude Code',
        )
