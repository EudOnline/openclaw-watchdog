from pathlib import Path

from openclaw_watchdog.rescue_agents.base import Runner, StructuredCliAdapter


class GeminiCliAdapter(StructuredCliAdapter):
    def __init__(
        self,
        *,
        available: bool = False,
        command: str = 'gemini',
        runner: Runner | None = None,
        timeout_seconds: int = 120,
        cwd: Path | None = None,
    ) -> None:
        super().__init__(
            name='gemini-cli',
            command=command,
            prompt_args=('-p',),
            available=available,
            runner=runner,
            timeout_seconds=timeout_seconds,
            cwd=cwd,
            provider_label='Gemini CLI',
        )
