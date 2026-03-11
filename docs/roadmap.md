# Roadmap

This roadmap now assumes the current internal seams are in place: typed models, presenters, a single rescue-first flow, a run context, a white-listed rescue action boundary, and a step-based bootstrap pipeline. Future work should build on those seams instead of collapsing logic back into `watchdog_v2/engine.py` or `watchdog_v2/cli.py`.

## Near-term follow-up

- deepen direct flow coverage for restart, rollback, survival, and rescue-dispatch branches
- improve the external CLI adapters so `Codex`, `Claude Code`, `Gemini CLI`, and `OpenCode` can return structured rescue plans without arbitrary shell access
- expand rehearsal smoke coverage only for scenarios that represent real operator risk
- keep report / metrics operationally useful and remove stale fields whenever they stop serving the OpenClaw rescue chain
- continue improving deployment docs and host onboarding guidance

## Validation policy

Every substantial change should keep these layers green:

1. unit + focused output tests under `tests/`
2. direct orchestration tests for flows / bootstrap steps
3. bounded rehearsal smoke scenarios
4. live acceptance on a real host when behavior or docs change materially

## Non-goals for now

- renaming the internal `watchdog_v2` package
- introducing a framework or dependency injection container
- turning the watchdog into a hosted incident-management product
