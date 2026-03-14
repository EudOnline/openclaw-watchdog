from pathlib import Path

from openclaw_watchdog.rescue_agents.base import Runner, StructuredCliAdapter


class CodexAdapter(StructuredCliAdapter):
    def __init__(
        self,
        *,
        available: bool = False,
        command: str = 'codex',
        runner: Runner | None = None,
        timeout_seconds: int = 120,
        cwd: Path | None = None,
    ) -> None:
        super().__init__(
            name='codex',
            command=command,
            prompt_args=('exec',),
            available=available,
            runner=runner,
            timeout_seconds=timeout_seconds,
            cwd=cwd,
            provider_label='Codex',
        )
