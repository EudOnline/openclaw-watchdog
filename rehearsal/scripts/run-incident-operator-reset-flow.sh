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

scripts/openclaw-watchdog --env "$ENV_FILE" incidents assign "$INCIDENT_ID" --owner alice >/dev/null
scripts/openclaw-watchdog --env "$ENV_FILE" incidents ack "$INCIDENT_ID" --by alice --note "investigating restart failure" >/dev/null
scripts/openclaw-watchdog --env "$ENV_FILE" incidents note "$INCIDENT_ID" --by bob --message "waiting for fallback result" >/dev/null
scripts/openclaw-watchdog --env "$ENV_FILE" incidents unassign "$INCIDENT_ID" >/dev/null
scripts/openclaw-watchdog --env "$ENV_FILE" incidents unack "$INCIDENT_ID" >/dev/null

LIST_ALL=$(scripts/openclaw-watchdog --env "$ENV_FILE" incidents list --json --limit 5)
LIST_OWNER_ALICE=$(scripts/openclaw-watchdog --env "$ENV_FILE" incidents list --json --owner alice --limit 5)
LIST_ACK_YES=$(scripts/openclaw-watchdog --env "$ENV_FILE" incidents list --json --ack yes --limit 5)
LIST_ACK_NO=$(scripts/openclaw-watchdog --env "$ENV_FILE" incidents list --json --ack no --limit 5)
SHOW_JSON=$(scripts/openclaw-watchdog --env "$ENV_FILE" incidents show "$INCIDENT_ID" --json)
REPORT_JSON=$(scripts/openclaw-watchdog --env "$ENV_FILE" report --json --limit 3)

python3 - <<'PY' "$INCIDENT_ID" "$LIST_ALL" "$LIST_OWNER_ALICE" "$LIST_ACK_YES" "$LIST_ACK_NO" "$SHOW_JSON" "$REPORT_JSON"
import json
import sys
incident_id = sys.argv[1]
list_all = json.loads(sys.argv[2])
list_owner_alice = json.loads(sys.argv[3])
list_ack_yes = json.loads(sys.argv[4])
list_ack_no = json.loads(sys.argv[5])
show_json = json.loads(sys.argv[6])
report_json = json.loads(sys.argv[7])
print(json.dumps({
    "incident_id": incident_id,
    "show": show_json,
    "list_all_count": len(list_all.get("incidents", [])),
    "list_owner_alice_count": len(list_owner_alice.get("incidents", [])),
    "list_ack_yes_count": len(list_ack_yes.get("incidents", [])),
    "list_ack_no_count": len(list_ack_no.get("incidents", [])),
    "list_ack_no_first_incident_id": ((list_ack_no.get("incidents") or [{}])[0]).get("incident_id", ""),
    "report_message_text": report_json.get("message_text", ""),
    "recent_incident_summary": ((report_json.get("recent_incidents") or [{}])[-1]).get("summary", ""),
}, ensure_ascii=False, indent=2))
PY
