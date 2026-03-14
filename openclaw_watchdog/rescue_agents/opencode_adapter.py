from pathlib import Path

from openclaw_watchdog.rescue_agents.base import Runner, StructuredCliAdapter


class OpenCodeAdapter(StructuredCliAdapter):
    def __init__(
        self,
        *,
        available: bool = False,
        command: str = 'opencode',
        runner: Runner | None = None,
        timeout_seconds: int = 120,
        cwd: Path | None = None,
    ) -> None:
        super().__init__(
            name='opencode',
            command=command,
            prompt_args=('run',),
            available=available,
            runner=runner,
            timeout_seconds=timeout_seconds,
            cwd=cwd,
            provider_label='OpenCode',
        )
