# First deployment

This guide is for the first safe rollout of the OpenClaw fallback system on a host that already has OpenClaw installed.

## Goal

Move from source checkout to a validated fallback deployment without immediately enabling aggressive repair behavior.

Operator quick path for the first rollout:

`detect -> check -> status --summary -> report --message -> scripts/openclaw-watchdog-live-acceptance.sh`

If you are validating the next public release candidate, pair this guide with [release-readiness.md](release-readiness.md). The current planned next release is `v0.2.0`, and the live acceptance artifacts from this guide are part of that gate.

## Minimum safe rollout

### 1. Clone and prepare the repo

Make sure the host has Python 3.11+ available. The `scripts/openclaw-watchdog` wrapper checks this before it imports the package and accepts any compatible interpreter it can discover under names such as `python3.11`, `python3.12`, `python3.13`, or a compatible `python3`.

```bash
git clone https://github.com/EudOnline/openclaw-watchdog ~/openclaw-watchdog
cd ~/openclaw-watchdog
cp config/openclaw-watchdog.env.example config/openclaw-watchdog.env
chmod +x scripts/openclaw-watchdog scripts/install-openclaw-watchdog-units.sh scripts/install-openclaw-watchdog-launchd.sh
```

### 2. Keep the first rollout conservative

The built-in defaults now mirror the sample env for home-directory paths and keep risky first-rollout automation conservative unless you explicitly opt in.

Keep these values off for the first live deployment:

- `WATCHDOG_ENABLE_PRE_REPAIR_BACKUP=false`
- `WATCHDOG_ENABLE_SURVIVABILITY_FLOW=false`
- `WATCHDOG_ENABLE_SURVIVAL_MODE=false`

### 3. Run host detection first

```bash
scripts/openclaw-watchdog detect
```

This command is **detect-only**. It does not enable repair actions or mutate the live deployment, and it does not install missing rescue tools.

It inspects the current host and reports:

- whether `openclaw` is installed
- whether the configured OpenClaw config path exists
- the configured gateway service and inferred port
- whether the watchdog state directory looks writable
- which core host commands are available
- configured / active conversation channels
- suggested primary conversation targets

### 4. Optionally write a suggested config fragment

```bash
scripts/openclaw-watchdog detect \
  --write-suggested-config config/openclaw-watchdog.detected.env
```

Review the generated file before merging any values into your main config.

The live rescue order remains fixed:

- `codex`
- `claude-code`
- `gemini-cli`
- `opencode`
- `litellm`
- `rule-agent`

If one tier is missing or unavailable, the fallback system skips it and continues. The deployment path does not auto-install any of these tools.

Canonical rescue chain is fixed in code: `codex -> claude-code -> gemini-cli -> opencode -> litellm -> rule-agent`.

### 5. Review the main env file

**Required before first live run**

- `OPENCLAW_CONFIG`
- `OPENCLAW_GATEWAY_SERVICE`
- `OPENCLAW_GATEWAY_PORT`
- `WATCHDOG_PRIMARY_CONVERSATION_TARGETS`

**Recommended to confirm before enabling automation**

- `WATCHDOG_STATE_DIR`
- `WATCHDOG_INCIDENTS_DIR`
- `WATCHDOG_LAST_REPORT_FILE`
- `WATCHDOG_LAST_METRICS_FILE`
- `WATCHDOG_NOTIFY_CHANNEL`
- `WATCHDOG_NOTIFY_TARGET`
- `WATCHDOG_RESCUE_EDITABLE_PATHS`
- `WATCHDOG_RESCUE_EDITABLE_KEYS`

**Leave conservative on the first rollout**

- `WATCHDOG_ENABLE_PRE_REPAIR_BACKUP=false`
- `WATCHDOG_ENABLE_SURVIVABILITY_FLOW=false`
- `WATCHDOG_ENABLE_SURVIVAL_MODE=false`

### 6. Run read-only checks before enabling the timer

```bash
scripts/openclaw-watchdog check --env config/openclaw-watchdog.env
scripts/openclaw-watchdog status --env config/openclaw-watchdog.env --summary
scripts/openclaw-watchdog report --env config/openclaw-watchdog.env --message
```

Review the output and confirm that:

- the configured gateway service and config path are correct;
- the state and incident directories are writable;
- the reported conversation targets match what you intend to recover;
- the rescue order and available executors match the tools already installed on the host;
- the editable path/key boundary only covers the OpenClaw files and namespaces you are willing to let rescue mutate;
- the summary/report output is understandable enough for an operator to act on.

### 7. Enable systemd user units only after review

```bash
scripts/install-openclaw-watchdog-units.sh
systemctl --user enable --now openclaw-watchdog.timer
```

Experimental macOS note:

- the repo now also ships a `launchd` installer at `scripts/install-openclaw-watchdog-launchd.sh`
- that path is intended for experimental macOS adapter validation only
- keep first real production rollouts on Linux + `systemd --user` until macOS has its own live acceptance evidence

### 8. Run live acceptance on the real host

```bash
./scripts/openclaw-watchdog-live-acceptance.sh
```

Use this only after the earlier read-only checks look sane. The live acceptance pass is still read-only from the operator perspective and is meant to confirm that `status`, `report`, `metrics`, and incident surfaces agree about the current fallback state.

For release signoff, keep the generated `docs/p7a-live/` artifacts from the candidate host and reference them from the current release notes draft instead of relying on memory.

### 9. Confirm the timer-backed deployment

```bash
systemctl --user status openclaw-watchdog.timer
systemctl --user status openclaw-watchdog.service
scripts/openclaw-watchdog status --env config/openclaw-watchdog.env --summary
scripts/openclaw-watchdog report --env config/openclaw-watchdog.env --message
```

## Notes

If you want the full recovery sequence in one place before enabling live automation, read [rescue-lifecycle.md](rescue-lifecycle.md).


- `detect` is meant to reduce first-run guesswork, not to silently auto-configure a production host.
- the deployment path does not install missing rescue tools; install and verify each desired executor yourself before relying on that tier.
- If the wrapper reports that no compatible interpreter was found, install Python 3.11+ before proceeding.
- Only enable more aggressive automation after the conservative path above looks correct on the real host.
- Treat the live acceptance output as the final rollout gate before you trust unattended timer runs on that host.
