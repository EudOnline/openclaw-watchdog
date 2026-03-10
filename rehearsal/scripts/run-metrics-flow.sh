#!/usr/bin/env bash
set -euo pipefail

MODE="${1:-healthy}"
ENV_FILE="${2:-rehearsal/env/openclaw-watchdog-v2.rehearsal.env}"

case "$MODE" in
  healthy)
    scripts/openclaw-watchdog-v2 --env "$ENV_FILE" run-once --json >/dev/null
    scripts/openclaw-watchdog-v2 --env "$ENV_FILE" metrics --json
    ;;
  open)
    set +e
    scripts/openclaw-watchdog-v2 --env "$ENV_FILE" run-once --json >/dev/null
    set -e
    scripts/openclaw-watchdog-v2 --env "$ENV_FILE" metrics --json
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
    scripts/openclaw-watchdog-v2 --env "$ENV_FILE" metrics --json
    ;;
  operator-open)
    set +e
    scripts/openclaw-watchdog-v2 --env "$ENV_FILE" run-once --json >/dev/null
    set -e
    INCIDENT_ID=$(python3 - <<'PY'
import json
from pathlib import Path
p = Path('rehearsal/runtime/watchdog/incident-index.json')
items = json.loads(p.read_text(encoding='utf-8')) if p.exists() else []
print(items[-1]['incident_id'] if items else '')
PY
)
    test -n "$INCIDENT_ID"
    scripts/openclaw-watchdog-v2 --env "$ENV_FILE" incidents assign "$INCIDENT_ID" --owner alice >/dev/null
    scripts/openclaw-watchdog-v2 --env "$ENV_FILE" incidents ack "$INCIDENT_ID" --by alice --note "investigating exporter view" >/dev/null
    scripts/openclaw-watchdog-v2 --env "$ENV_FILE" incidents note "$INCIDENT_ID" --by bob --message "collector should see operator context" >/dev/null
    scripts/openclaw-watchdog-v2 --env "$ENV_FILE" metrics --json
    ;;
  *)
    echo "Unknown mode: $MODE" >&2
    exit 1
    ;;
esac
