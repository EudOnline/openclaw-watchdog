# macOS launchd rollout guide

This guide defines the narrow macOS rollout shape that the repository currently supports for adapter validation and future release gating.

## Supported macOS shape

The supported macOS path in this repository is a per-user `LaunchAgent` running in `gui/$UID`.

Set `OPENCLAW_GATEWAY_SERVICE` to the `launchd` label used by the local OpenClaw gateway, for example `com.openclaw.gateway`.

The watchdog agent label remains `com.eudonline.openclaw-watchdog`, and the repo installer targets:

- `~/Library/LaunchAgents/com.eudonline.openclaw-watchdog.plist`
- `gui/$UID/com.eudonline.openclaw-watchdog`

LaunchDaemon is out of scope for this release batch.

## What this guide is for

Use this guide when you want to:

- validate the macOS `launchd` adapter on a real Darwin host;
- keep the service-label contract explicit instead of reusing Linux `.service` names;
- prepare future macOS live-acceptance evidence without widening the support claim too early.

This guide does not change the current production baseline. Linux + `systemd --user` remains the only live-validated rollout path today.

## Minimum macOS rollout path

1. start from the repo-local install flow in [first-deployment.md](first-deployment.md);
2. confirm that `OPENCLAW_GATEWAY_SERVICE` is a macOS `launchd` label such as `com.openclaw.gateway`;
3. install the watchdog LaunchAgent with `scripts/install-openclaw-watchdog-launchd.sh`;
4. inspect both the watchdog and gateway labels with `launchctl print`;
5. keep any acceptance evidence under `docs/p7a-live/` once the host gate is ready.

## Useful commands

```bash
scripts/install-openclaw-watchdog-launchd.sh
launchctl print gui/$UID/com.eudonline.openclaw-watchdog
launchctl print gui/$UID/com.openclaw.gateway
launchctl kickstart -k gui/$UID/com.eudonline.openclaw-watchdog
```

## Current status

Treat this path as a narrow macOS rollout contract, not as a broad compatibility promise. Until real-host evidence is attached to the release gate, keep describing the macOS path as experimental in public release claims.
