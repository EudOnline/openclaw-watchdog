# First deployment

This guide is for the first safe rollout on a host that already has OpenClaw installed.

## Goal

Move from source checkout to a validated watchdog deployment without immediately enabling aggressive repair behavior.

## Suggested sequence

### 1. Clone and prepare the repo

```bash
git clone https://github.com/EudOnline/openclaw-watchdog ~/openclaw-watchdog
cd ~/openclaw-watchdog
cp config/openclaw-watchdog.env.example config/openclaw-watchdog.env
```

### 2. Run host detection

```bash
scripts/openclaw-watchdog detect
```

This command is **detect-only**. It does not enable repair actions or mutate the live deployment.

It inspects the current host and reports:

- whether `openclaw` is installed
- whether the configured OpenClaw config path exists
- the configured gateway service and inferred port
- whether the watchdog state directory looks writable
- which core host commands are available
- configured / active conversation channels
- suggested primary conversation targets

### 3. Optionally write a suggested config fragment

```bash
scripts/openclaw-watchdog detect \
  --write-suggested-config config/openclaw-watchdog.detected.env
```

Review the generated file before merging any values into your main config.

### 4. Review your main env file

At minimum, confirm these values:

- `OPENCLAW_CONFIG`
- `OPENCLAW_GATEWAY_SERVICE`
- `OPENCLAW_GATEWAY_PORT`
- `WATCHDOG_PRIMARY_CONVERSATION_TARGETS`

### 5. Run a health check

```bash
scripts/openclaw-watchdog check --env config/openclaw-watchdog.env
```

### 6. Enable systemd user units only after review

```bash
scripts/install-openclaw-watchdog-units.sh
systemctl --user enable --now openclaw-watchdog.timer
```

## Notes

- `detect` is meant to reduce first-run guesswork, not to silently auto-configure a production host.
- Future work will add preflight and observe-first rollout guidance on top of this detect-only foundation.
