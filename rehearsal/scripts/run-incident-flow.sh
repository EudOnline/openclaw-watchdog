#!/usr/bin/env bash
set -euo pipefail

MODE="${1:-open}"
ENV_FILE="${2:-rehearsal/env/openclaw-watchdog-v2.rehearsal.env}"

case "$MODE" in
  open)
    set +e
    scripts/openclaw-watchdog-v2 --env "$ENV_FILE" run-once --json >/dev/null
    set -e
    scripts/openclaw-watchdog-v2 --env "$ENV_FILE" incidents current --json
    ;;
  resolved)
    set +e
    scripts/openclaw-watchdog-v2 --env "$ENV_FILE" run-once --json >/dev/null
    set -e
    python3 - <<'PY'
import json
from pathlib import Path
p = Path('rehearsal/runtime/shim-state.json')
data = json.loads(p.read_text(encoding='utf-8'))
data.update({
    'service_active': True,
    'main_pid': '4601',
    'listener_pids': ['4601'],
    'service_level_reachable': True,
    'restart_mode': 'healthy',
})
p.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding='utf-8')
PY
    scripts/openclaw-watchdog-v2 --env "$ENV_FILE" run-once --json >/dev/null
    INCIDENT_ID=$(python3 - <<'PY'
import json
from pathlib import Path
p = Path('rehearsal/runtime/watchdog/incident-index.json')
items = json.loads(p.read_text(encoding='utf-8')) if p.exists() else []
print(items[-1]['incident_id'] if items else '')
PY
)
    test -n "$INCIDENT_ID"
    scripts/openclaw-watchdog-v2 --env "$ENV_FILE" incidents show "$INCIDENT_ID" --json
    ;;
  *)
    echo "Unknown mode: $MODE" >&2
    exit 1
    ;;
esac
