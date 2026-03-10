# Roadmap

This roadmap focuses on practical operator value: better recovery behavior, clearer validation paths, and a cleaner public project surface.

## v0.2.0 — usability and polish

- Refine the public README front page further
- Reduce remaining migration friction around deprecated shim scripts
- Improve docs around installation, validation, and expected host layout
- Add stronger examples for systemd deployment and operator workflows

## v0.3.0 — validation and packaging

- Add host auto-detection and preflight onboarding for safer first deployment
- Expand rehearsal coverage for common recovery paths
- Add a more explicit test/validation matrix
- Improve packaging ergonomics for source-based installation
- Consider lightweight release artifacts if maintenance cost stays reasonable

A likely shape for this work is: detect host -> suggest config -> preflight -> observe-only rollout -> promote to active repair.

## Future directions

- Stronger drift-guard and rollback guidance
- Better release engineering and changelog discipline
- More operator-focused examples for recovery, metrics, and incident triage
- Clearer separation between core watchdog behavior and optional helper workflows

## Non-goals for now

- Shipping a complex hosted service around the watchdog
- Turning the project into a full incident-management platform
- Renaming the internal `watchdog_v2` Python package unless the migration value clearly outweighs the churn
