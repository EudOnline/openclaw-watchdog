#!/usr/bin/env bash
set -euo pipefail

SCENARIO_NAME="${1:?scenario name required}"
ENV_FILE="${2:?env file required}"

TMP_DIR="rehearsal/runtime/tmp/survivability-flow-${SCENARIO_NAME}-$$"
mkdir -p "$TMP_DIR"
OUTCOME_FILE="$TMP_DIR/outcome.json"
STATUS_FILE="$TMP_DIR/status.json"
REPORT_FILE="$TMP_DIR/report.json"
METRICS_FILE="$TMP_DIR/metrics.json"

cleanup() {
  rm -f "$OUTCOME_FILE" "$STATUS_FILE" "$REPORT_FILE" "$METRICS_FILE"
  rmdir "$TMP_DIR" 2>/dev/null || true
}
trap cleanup EXIT

scripts/openclaw-watchdog --env "$ENV_FILE" run-once --json > "$OUTCOME_FILE"
scripts/openclaw-watchdog --env "$ENV_FILE" status --json > "$STATUS_FILE"
scripts/openclaw-watchdog --env "$ENV_FILE" report --json > "$REPORT_FILE"
scripts/openclaw-watchdog --env "$ENV_FILE" metrics --json > "$METRICS_FILE"

python3 - <<'PY' "$SCENARIO_NAME" "$OUTCOME_FILE" "$STATUS_FILE" "$REPORT_FILE" "$METRICS_FILE"
from __future__ import annotations

import json
import sys
from pathlib import Path

scenario_name = sys.argv[1]
outcome = json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))
status = json.loads(Path(sys.argv[3]).read_text(encoding="utf-8"))
report = json.loads(Path(sys.argv[4]).read_text(encoding="utf-8"))
metrics = json.loads(Path(sys.argv[5]).read_text(encoding="utf-8"))
messages_log = Path("rehearsal/runtime/logs/messages.log").read_text(encoding="utf-8")
watchdog_log = Path("rehearsal/runtime/watchdog/watchdog.log").read_text(encoding="utf-8")

print(
    json.dumps(
        {
            "scenario": scenario_name,
            "outcome": outcome,
            "status": status,
            "report": report,
            "metrics": metrics,
            "messages_log": messages_log,
            "watchdog_log": watchdog_log,
        },
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
    )
)
PY
