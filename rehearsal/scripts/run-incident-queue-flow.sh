#!/usr/bin/env bash
set -euo pipefail

ENV_FILE="${1:-rehearsal/env/openclaw-watchdog-v2.rehearsal.env}"

get_last_incident_id() {
  python3 - <<'PY'
import json
from pathlib import Path
p = Path('rehearsal/runtime/watchdog/incident-index.json')
items = json.loads(p.read_text(encoding='utf-8')) if p.exists() else []
print(items[-1]['incident_id'] if items else '')
PY
}

set +e
scripts/openclaw-watchdog-v2 --env "$ENV_FILE" run-once --json >/dev/null
set -e
INCIDENT_ID="$(get_last_incident_id)"
test -n "$INCIDENT_ID"
QUEUE_OPEN=$(scripts/openclaw-watchdog-v2 --env "$ENV_FILE" incidents queue --json --limit 10)
STATUS_OPEN=$(scripts/openclaw-watchdog-v2 --env "$ENV_FILE" status --json)
REPORT_OPEN=$(scripts/openclaw-watchdog-v2 --env "$ENV_FILE" report --json --limit 3)

scripts/openclaw-watchdog-v2 --env "$ENV_FILE" incidents assign "$INCIDENT_ID" --owner alice >/dev/null
scripts/openclaw-watchdog-v2 --env "$ENV_FILE" incidents ack "$INCIDENT_ID" --by alice --note "queue picked up" >/dev/null
QUEUE_HANDLED=$(scripts/openclaw-watchdog-v2 --env "$ENV_FILE" incidents queue --json --limit 10)

python3 - <<'PY' "$QUEUE_OPEN" "$STATUS_OPEN" "$REPORT_OPEN" "$QUEUE_HANDLED"
import json
import sys
queue_open = json.loads(sys.argv[1])
status_open = json.loads(sys.argv[2])
report_open = json.loads(sys.argv[3])
queue_handled = json.loads(sys.argv[4])
print(json.dumps({
    'queue_open': queue_open,
    'status_open_summary': status_open.get('incident_queue_summary', {}),
    'report_open_summary': report_open.get('incident_queue_summary', {}),
    'queue_handled': queue_handled,
}, ensure_ascii=False, indent=2))
PY
