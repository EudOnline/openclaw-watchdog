# Roadmap

This roadmap now assumes the current internal seams are in place: typed models, presenters, flow modules, a run context, and a step-based bootstrap pipeline. Future work should build on those seams instead of collapsing logic back into `watchdog_v2/engine.py` or `watchdog_v2/cli.py`.

## Near-term follow-up

- deepen direct flow coverage for restart, rollback, and escalation branches
- expand rehearsal smoke coverage only for scenarios that represent real operator risk
- keep the reporting / metrics contract stable while tightening internal types further
- continue improving deployment docs and host onboarding guidance

## Validation policy

Every substantial change should keep these layers green:

1. unit + contract tests under `tests/`
2. direct orchestration tests for flows / bootstrap steps
3. bounded rehearsal smoke scenarios
4. live acceptance on a real host when behavior or docs change materially

## Non-goals for now

- renaming the internal `watchdog_v2` package
- introducing a framework or dependency injection container
- turning the watchdog into a hosted incident-management product
