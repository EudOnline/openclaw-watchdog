#!/usr/bin/env bash
set -euo pipefail

ENV_FILE="${1:-rehearsal/env/openclaw-watchdog.rehearsal.env}"

export WATCHDOG_ENABLE_SURVIVABILITY_FLOW="true"
export WATCHDOG_ENABLE_SURVIVAL_MODE="true"
export WATCHDOG_SURVIVAL_STABLE_READY_RUNS="1"

FIRST_OUTCOME=$(scripts/openclaw-watchdog --env "$ENV_FILE" run-once --json)
PENDING_OUTCOME=$(scripts/openclaw-watchdog --env "$ENV_FILE" run-once --json)
PENDING_STATUS=$(scripts/openclaw-watchdog --env "$ENV_FILE" status --json)
PENDING_REPORT=$(scripts/openclaw-watchdog --env "$ENV_FILE" report --json)

cp rehearsal/fixtures/healthy-openclaw-config.json "$OPENCLAW_CONFIG"
python3 - <<'PY'
from __future__ import annotations

import json
from pathlib import Path

path = Path('rehearsal/runtime/shim-state.json')
state = json.loads(path.read_text(encoding='utf-8'))
state.update(
    {
        'service_active': True,
        'main_pid': '5003',
        'listener_pids': ['5003'],
        'service_level_reachable': True,
        'conversation_ready': True,
        'minimal_usable_ready': True,
        'conversation_summary': 'operator replaced the survival config with a stable full-ready config',
        'channel_summary': ['QQ Bot: configured', 'Feishu: configured'],
        'restart_mode': 'healthy',
        'survival_recovery_mode': '',
    }
)
path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding='utf-8')
PY

FINAL_OUTCOME=$(scripts/openclaw-watchdog --env "$ENV_FILE" run-once --json)
FINAL_STATUS=$(scripts/openclaw-watchdog --env "$ENV_FILE" status --json)
FINAL_REPORT=$(scripts/openclaw-watchdog --env "$ENV_FILE" report --json)
FINAL_METRICS=$(scripts/openclaw-watchdog --env "$ENV_FILE" metrics --json)

python3 - <<'PY' "$FIRST_OUTCOME" "$PENDING_OUTCOME" "$PENDING_STATUS" "$PENDING_REPORT" "$FINAL_OUTCOME" "$FINAL_STATUS" "$FINAL_REPORT" "$FINAL_METRICS"
from __future__ import annotations

import json
import sys
from pathlib import Path

print(
    json.dumps(
        {
            'first_outcome': json.loads(sys.argv[1]),
            'pending_outcome': json.loads(sys.argv[2]),
            'pending_status': json.loads(sys.argv[3]),
            'pending_report': json.loads(sys.argv[4]),
            'final_outcome': json.loads(sys.argv[5]),
            'final_status': json.loads(sys.argv[6]),
            'final_report': json.loads(sys.argv[7]),
            'final_metrics': json.loads(sys.argv[8]),
            'survival_state': json.loads(Path('rehearsal/runtime/watchdog/survival-mode.json').read_text(encoding='utf-8')),
        },
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
    )
)
PY
