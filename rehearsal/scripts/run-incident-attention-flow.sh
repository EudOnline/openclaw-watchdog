#!/usr/bin/env bash
set -euo pipefail

ENV_FILE="${1:-rehearsal/env/openclaw-watchdog.rehearsal.env}"

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
scripts/openclaw-watchdog --env "$ENV_FILE" run-once --json >/dev/null
set -e
INCIDENT_ID="$(get_last_incident_id)"
test -n "$INCIDENT_ID"

LIST_YES=$(scripts/openclaw-watchdog --env "$ENV_FILE" incidents list --json --attention yes --limit 5)
SHOW_OPEN=$(scripts/openclaw-watchdog --env "$ENV_FILE" incidents show "$INCIDENT_ID" --json)

scripts/openclaw-watchdog --env "$ENV_FILE" incidents assign "$INCIDENT_ID" --owner alice >/dev/null
scripts/openclaw-watchdog --env "$ENV_FILE" incidents ack "$INCIDENT_ID" --by alice --note "triaging attention queue" >/dev/null

LIST_NO=$(scripts/openclaw-watchdog --env "$ENV_FILE" incidents list --json --attention no --limit 5)
CURRENT_JSON=$(scripts/openclaw-watchdog --env "$ENV_FILE" incidents current --json)
STATUS_JSON=$(scripts/openclaw-watchdog --env "$ENV_FILE" status --json)
REPORT_JSON=$(scripts/openclaw-watchdog --env "$ENV_FILE" report --json --limit 3)

python3 - <<'PY' "$INCIDENT_ID" "$LIST_YES" "$SHOW_OPEN" "$LIST_NO" "$CURRENT_JSON" "$STATUS_JSON" "$REPORT_JSON"
import json
import sys
incident_id = sys.argv[1]
list_yes = json.loads(sys.argv[2])
show_open = json.loads(sys.argv[3])
list_no = json.loads(sys.argv[4])
current_json = json.loads(sys.argv[5])
status_json = json.loads(sys.argv[6])
report_json = json.loads(sys.argv[7])
recent_incidents = status_json.get('recent_incidents', [])
first_recent = recent_incidents[-1] if recent_incidents else {}
print(json.dumps({
    'incident_id': incident_id,
    'list_yes_count': len(list_yes.get('incidents', [])),
    'show_open': show_open,
    'list_no_count': len(list_no.get('incidents', [])),
    'current': current_json,
    'status_recent_incident': first_recent,
    'report_message_text': report_json.get('message_text', ''),
}, ensure_ascii=False, indent=2))
PY
