#!/usr/bin/env bash
set -euo pipefail

MODE="${1:?mode required}"
ENV_SOURCE="${2:-rehearsal/env/openclaw-watchdog-v2.rehearsal.env}"
ENV_FILE="rehearsal/runtime/watchdog-drift-${MODE}.env"

mkdir -p "$(dirname "$ENV_FILE")"
cp "$ENV_SOURCE" "$ENV_FILE"

export WATCHDOG_ENABLE_SURVIVABILITY_FLOW="true"
export WATCHDOG_ENABLE_SURVIVAL_MODE="true"

EXT_DIR="$(dirname "$OPENCLAW_CONFIG")/extensions/qqbot"
EXT_FILE="$EXT_DIR/index.js"

mkdir -p "$EXT_DIR"
cat > "$EXT_FILE" <<'EOF'
console.log('baseline plugin fixture');
EOF

BASELINE_OUTCOME=$(scripts/openclaw-watchdog-v2 --env "$ENV_FILE" run-once --json)

case "$MODE" in
  env)
    python3 - <<'PY' "$ENV_FILE"
from __future__ import annotations

import sys
from pathlib import Path

path = Path(sys.argv[1])
lines = path.read_text(encoding='utf-8').splitlines()
rewritten = []
for line in lines:
    if line.startswith('WATCHDOG_NOTIFY_TARGET='):
        rewritten.append('WATCHDOG_NOTIFY_TARGET="drifted-target"')
    else:
        rewritten.append(line)
path.write_text("\n".join(rewritten) + "\n", encoding='utf-8')
PY
    ;;
  plugin)
    cat > "$EXT_FILE" <<'EOF'
console.log('drifted plugin fixture');
EOF
    ;;
  *)
    echo "Unknown mode: $MODE" >&2
    exit 1
    ;;
esac

python3 - <<'PY'
from __future__ import annotations

import json
from pathlib import Path

path = Path('rehearsal/runtime/shim-state.json')
state = json.loads(path.read_text(encoding='utf-8'))
state.update(
    {
        'service_active': False,
        'main_pid': '0',
        'listener_pids': [],
        'service_level_reachable': False,
        'conversation_ready': False,
        'minimal_usable_ready': False,
        'conversation_summary': 'protected-path drift should prefer rollback before doctor repair',
        'restart_mode': 'inactive',
        'restart_mode_sequence': ['inactive', 'healthy'],
        'restart_profile_sequence': ['down', 'ready'],
        'survival_recovery_mode': '',
    }
)
path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding='utf-8')
PY

RECOVERY_OUTCOME=$(scripts/openclaw-watchdog-v2 --env "$ENV_FILE" run-once --json)
STATUS_JSON=$(scripts/openclaw-watchdog-v2 --env "$ENV_FILE" status --json)
REPORT_JSON=$(scripts/openclaw-watchdog-v2 --env "$ENV_FILE" report --json)
METRICS_JSON=$(scripts/openclaw-watchdog-v2 --env "$ENV_FILE" metrics --json)

python3 - <<'PY' "$MODE" "$BASELINE_OUTCOME" "$RECOVERY_OUTCOME" "$STATUS_JSON" "$REPORT_JSON" "$METRICS_JSON" "$ENV_FILE" "$EXT_FILE"
from __future__ import annotations

import json
import sys
from pathlib import Path

payload = {
    'mode': sys.argv[1],
    'baseline_outcome': json.loads(sys.argv[2]),
    'recovery_outcome': json.loads(sys.argv[3]),
    'status': json.loads(sys.argv[4]),
    'report': json.loads(sys.argv[5]),
    'metrics': json.loads(sys.argv[6]),
    'env_file_text': Path(sys.argv[7]).read_text(encoding='utf-8'),
    'plugin_file_text': Path(sys.argv[8]).read_text(encoding='utf-8'),
    'guard_manifest': json.loads(Path('rehearsal/runtime/watchdog/drift-guard.json').read_text(encoding='utf-8')),
}
print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
PY
