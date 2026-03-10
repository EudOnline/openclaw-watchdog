#!/usr/bin/env bash
set -euo pipefail

ENV_FILE="${1:-rehearsal/env/openclaw-watchdog-v2.rehearsal.env}"
TMP_DIR="rehearsal/runtime/scenario-output/watchdog-incident-notes-query"
mkdir -p "$TMP_DIR"

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

scripts/openclaw-watchdog-v2 --env "$ENV_FILE" incidents assign "$INCIDENT_ID" --owner alice >/dev/null
scripts/openclaw-watchdog-v2 --env "$ENV_FILE" incidents ack "$INCIDENT_ID" --by alice --note "first operator note" >/dev/null
scripts/openclaw-watchdog-v2 --env "$ENV_FILE" incidents note "$INCIDENT_ID" --by bob --message "second operator note" >/dev/null
scripts/openclaw-watchdog-v2 --env "$ENV_FILE" incidents note "$INCIDENT_ID" --by carol --message "third operator note" >/dev/null
scripts/openclaw-watchdog-v2 --env "$ENV_FILE" incidents note "$INCIDENT_ID" --by dave --message "fourth operator note" >/dev/null

LIST_NOTES_YES=$(scripts/openclaw-watchdog-v2 --env "$ENV_FILE" incidents list --json --notes yes --limit 5)
LIST_NOTES_NO=$(scripts/openclaw-watchdog-v2 --env "$ENV_FILE" incidents list --json --notes no --limit 5)
SHOW_JSON=$(scripts/openclaw-watchdog-v2 --env "$ENV_FILE" incidents show "$INCIDENT_ID" --json)
TIMELINE_JSON=$(scripts/openclaw-watchdog-v2 --env "$ENV_FILE" incidents timeline "$INCIDENT_ID" --json --limit 3)
REPORT_JSON=$(scripts/openclaw-watchdog-v2 --env "$ENV_FILE" report --json --limit 3)
scripts/openclaw-watchdog-v2 --env "$ENV_FILE" incidents show "$INCIDENT_ID" > "$TMP_DIR/show-default.txt"
scripts/openclaw-watchdog-v2 --env "$ENV_FILE" incidents show "$INCIDENT_ID" --notes-all > "$TMP_DIR/show-all.txt"

python3 - <<'PY' "$INCIDENT_ID" "$LIST_NOTES_YES" "$LIST_NOTES_NO" "$SHOW_JSON" "$TIMELINE_JSON" "$REPORT_JSON" "$TMP_DIR/show-default.txt" "$TMP_DIR/show-all.txt"
import json
import sys
from pathlib import Path
incident_id = sys.argv[1]
list_notes_yes = json.loads(sys.argv[2])
list_notes_no = json.loads(sys.argv[3])
show_json = json.loads(sys.argv[4])
timeline_json = json.loads(sys.argv[5])
report_json = json.loads(sys.argv[6])
default_text = Path(sys.argv[7]).read_text(encoding='utf-8')
all_text = Path(sys.argv[8]).read_text(encoding='utf-8')
def count_note_lines(text: str) -> int:
    return sum(1 for line in text.splitlines() if line.startswith('note_'))
print(json.dumps({
    'incident_id': incident_id,
    'show': show_json,
    'list_notes_yes_count': len(list_notes_yes.get('incidents', [])),
    'list_notes_no_count': len(list_notes_no.get('incidents', [])),
    'timeline_limit_count': len(timeline_json.get('events', [])),
    'timeline_last_type': ((timeline_json.get('events') or [{}])[-1]).get('type', ''),
    'report_message_text': report_json.get('message_text', ''),
    'default_note_lines': count_note_lines(default_text),
    'all_note_lines': count_note_lines(all_text),
}, ensure_ascii=False, indent=2))
PY
