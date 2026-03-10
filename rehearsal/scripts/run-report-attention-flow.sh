#!/usr/bin/env bash
set -euo pipefail

MODE="${1:-open-unowned}"
ENV_FILE="${2:-rehearsal/env/openclaw-watchdog-v2.rehearsal.env}"

get_last_incident_id() {
  python3 - <<'PY'
import json
from pathlib import Path
p = Path('rehearsal/runtime/watchdog/incident-index.json')
items = json.loads(p.read_text(encoding='utf-8')) if p.exists() else []
print(items[-1]['incident_id'] if items else '')
PY
}

case "$MODE" in
  open-unowned)
    set +e
    scripts/openclaw-watchdog-v2 --env "$ENV_FILE" run-once --json >/dev/null
    set -e
    scripts/openclaw-watchdog-v2 --env "$ENV_FILE" report --json --limit 3
    ;;
  open-owned)
    set +e
    scripts/openclaw-watchdog-v2 --env "$ENV_FILE" run-once --json >/dev/null
    set -e
    INCIDENT_ID="$(get_last_incident_id)"
    test -n "$INCIDENT_ID"
    scripts/openclaw-watchdog-v2 --env "$ENV_FILE" incidents assign "$INCIDENT_ID" --owner alice >/dev/null
    scripts/openclaw-watchdog-v2 --env "$ENV_FILE" incidents ack "$INCIDENT_ID" --by alice --note "investigating attention clear" >/dev/null
    scripts/openclaw-watchdog-v2 --env "$ENV_FILE" report --json --limit 3
    ;;
  *)
    echo "Unknown mode: $MODE" >&2
    exit 1
    ;;
esac
