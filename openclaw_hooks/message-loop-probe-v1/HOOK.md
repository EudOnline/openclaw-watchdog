# Message Loop Probe V1

This hook writes `message:sent` and `message:received` events to a JSONL file so `openclaw_watchdog` can verify a real transport-level echo round trip.

## Why this hook exists

The watchdog's `status --json` and `health --json` probes are useful, but they are still indirect. This hook gives the watchdog a stronger signal: send a nonce-tagged probe message and only call the conversation path ready when a matching echo reply is observed in structured events.

## Required environment

- `WATCHDOG_MESSAGE_LOOP_PROBE_EVENTS_FILE`

The hook appends one JSON object per line to that path. The watchdog reads the same file via `WATCHDOG_MESSAGE_LOOP_PROBE_EVENTS_FILE` in its env config.

## Expected watchdog config

- `WATCHDOG_ENABLE_MESSAGE_LOOP_PROBE=true`
- `WATCHDOG_MESSAGE_LOOP_PROBE_CHANNEL=<your echo channel>`
- `WATCHDOG_MESSAGE_LOOP_PROBE_TARGET=<your echo target>`
- `WATCHDOG_MESSAGE_LOOP_PROBE_REPLY_FROM=<optional explicit echo sender>`
- `WATCHDOG_MESSAGE_LOOP_PROBE_EVENTS_FILE=<same JSONL path as this hook>`

## Installation outline

1. Copy or symlink this directory into your OpenClaw hooks directory.
2. Register the hook for `message:sent` and `message:received`.
3. Make sure the hook environment includes `WATCHDOG_MESSAGE_LOOP_PROBE_EVENTS_FILE`.
4. Point the watchdog env at the same JSONL file.

Use a dedicated echo account, bot, or test chat. Do not aim this probe at a human-operated conversation.
