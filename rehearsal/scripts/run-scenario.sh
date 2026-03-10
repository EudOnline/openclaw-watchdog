#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
SCENARIO="${1:-bootstrap-missing-openclaw}"
ENV_FILE="rehearsal/env/openclaw-watchdog.rehearsal.env"

cd "$REPO_ROOT"
export PYTHONPATH="$REPO_ROOT${PYTHONPATH:+:$PYTHONPATH}"
export HOME="$REPO_ROOT/rehearsal/runtime/home"
bash rehearsal/scripts/prepare-system-bin.sh >/dev/null
export PATH="$REPO_ROOT/rehearsal/bin:$REPO_ROOT/rehearsal/runtime/bin:$REPO_ROOT/rehearsal/system-bin"

set -a
source "$ENV_FILE"
source rehearsal/env/openclaw-backup.rehearsal.env
set +a

run_exact() {
  local scenario_name="$1"
  local expected_exit="$2"
  shift 2
  rehearsal/scripts/apply-scenario.sh "$scenario_name" >/dev/null
  local output_dir="rehearsal/runtime/scenario-output/$scenario_name"
  mkdir -p "$output_dir"
  local stdout_file="$output_dir/stdout.txt"
  local stderr_file="$output_dir/stderr.txt"
  local expected_file="rehearsal/scenarios/$scenario_name.expected.txt"
  printf '%q ' "$@" > "$output_dir/command.txt"
  echo >> "$output_dir/command.txt"
  set +e
  "$@" >"$stdout_file" 2>"$stderr_file"
  local exit_code="$?"
  set -e
  printf '%s\n' "$exit_code" > "$output_dir/exit_code.txt"
  if [[ "$exit_code" != "$expected_exit" ]]; then
    echo "Scenario $scenario_name failed: expected exit $expected_exit, got $exit_code" >&2
    exit 1
  fi
  diff -u "$expected_file" "$stdout_file"
  echo "Scenario $scenario_name passed"
  echo "  output: $stdout_file"
}

run_json() {
  local scenario_name="$1"
  local expected_exit="$2"
  local assertions_file="$3"
  shift 3
  rehearsal/scripts/apply-scenario.sh "$scenario_name" >/dev/null
  local output_dir="rehearsal/runtime/scenario-output/$scenario_name"
  mkdir -p "$output_dir"
  local stdout_file="$output_dir/stdout.json"
  local stderr_file="$output_dir/stderr.txt"
  printf '%q ' "$@" > "$output_dir/command.txt"
  echo >> "$output_dir/command.txt"
  set +e
  "$@" >"$stdout_file" 2>"$stderr_file"
  local exit_code="$?"
  set -e
  printf '%s\n' "$exit_code" > "$output_dir/exit_code.txt"
  python3 rehearsal/scripts/assert-json.py "$stdout_file" "$assertions_file" "$exit_code" "$expected_exit"
  echo "Scenario $scenario_name passed"
  echo "  output: $stdout_file"
}

case "$SCENARIO" in
  bootstrap-missing-openclaw)
    run_exact "$SCENARIO" 10 scripts/openclaw-watchdog --env "$ENV_FILE" bootstrap
    ;;
  bootstrap-openclaw-missing-plugin)
    run_exact "$SCENARIO" 0 scripts/openclaw-watchdog --env "$ENV_FILE" bootstrap
    ;;
  bootstrap-install-openclaw)
    run_exact "$SCENARIO" 0 scripts/openclaw-watchdog --env "$ENV_FILE" bootstrap --install-openclaw
    ;;
  watchdog-recovery)
    run_exact "$SCENARIO" 0 scripts/openclaw-watchdog --env "$ENV_FILE" run-once
    ;;
  watchdog-failed-fallback)
    run_json "$SCENARIO" 1 rehearsal/scenarios/watchdog-failed-fallback.assertions.json scripts/openclaw-watchdog --env "$ENV_FILE" run-once --json
    ;;
  watchdog-active-no-listener-grace)
    run_exact "$SCENARIO" 0 scripts/openclaw-watchdog --env "$ENV_FILE" run-once
    ;;
  watchdog-service-layer-degraded)
    run_exact "$SCENARIO" 0 scripts/openclaw-watchdog --env "$ENV_FILE" run-once
    ;;
  watchdog-service-layer-threshold-recovery)
    run_exact "$SCENARIO" 0 scripts/openclaw-watchdog --env "$ENV_FILE" run-once
    ;;
  watchdog-service-layer-transient-retry)
    run_exact "$SCENARIO" 0 scripts/openclaw-watchdog --env "$ENV_FILE" run-once
    ;;
  watchdog-conversation-probe-ready)
    run_json "$SCENARIO" 0 rehearsal/scenarios/watchdog-conversation-probe-ready.assertions.json env WATCHDOG_ENABLE_CONVERSATION_PROBE=true WATCHDOG_ENABLE_SURVIVABILITY_FLOW=true scripts/openclaw-watchdog --env "$ENV_FILE" check --json
    ;;
  watchdog-conversation-probe-minimal)
    run_json "$SCENARIO" 0 rehearsal/scenarios/watchdog-conversation-probe-minimal.assertions.json env WATCHDOG_ENABLE_CONVERSATION_PROBE=true WATCHDOG_ENABLE_SURVIVABILITY_FLOW=true scripts/openclaw-watchdog --env "$ENV_FILE" check --json
    ;;
  watchdog-conversation-probe-down)
    run_json "$SCENARIO" 1 rehearsal/scenarios/watchdog-conversation-probe-down.assertions.json env WATCHDOG_ENABLE_CONVERSATION_PROBE=true WATCHDOG_ENABLE_SURVIVABILITY_FLOW=true scripts/openclaw-watchdog --env "$ENV_FILE" check --json
    ;;
  watchdog-restart-priority-recovery)
    run_json "$SCENARIO" 0 rehearsal/scenarios/watchdog-restart-priority-recovery.assertions.json env WATCHDOG_ENABLE_CONVERSATION_PROBE=true WATCHDOG_ENABLE_SURVIVABILITY_FLOW=true bash rehearsal/scripts/run-survivability-flow.sh "$SCENARIO" "$ENV_FILE"
    ;;
  watchdog-rollback-priority-before-doctor)
    run_json "$SCENARIO" 0 rehearsal/scenarios/watchdog-rollback-priority-before-doctor.assertions.json env WATCHDOG_ENABLE_CONVERSATION_PROBE=true WATCHDOG_ENABLE_SURVIVABILITY_FLOW=true bash rehearsal/scripts/run-survivability-flow.sh "$SCENARIO" "$ENV_FILE"
    ;;
  watchdog-doctor-deferred-until-survival-fails)
    run_json "$SCENARIO" 0 rehearsal/scenarios/watchdog-doctor-deferred-until-survival-fails.assertions.json env WATCHDOG_ENABLE_CONVERSATION_PROBE=true WATCHDOG_ENABLE_SURVIVABILITY_FLOW=true bash rehearsal/scripts/run-survivability-flow.sh "$SCENARIO" "$ENV_FILE"
    ;;
  watchdog-survival-mode-recovery)
    run_json "$SCENARIO" 0 rehearsal/scenarios/watchdog-survival-mode-recovery.assertions.json env WATCHDOG_ENABLE_CONVERSATION_PROBE=true WATCHDOG_ENABLE_SURVIVABILITY_FLOW=true WATCHDOG_ENABLE_SURVIVAL_MODE=true bash rehearsal/scripts/run-survivability-flow.sh "$SCENARIO" "$ENV_FILE"
    ;;
  watchdog-survival-mode-sticky-until-stable)
    run_json "$SCENARIO" 0 rehearsal/scenarios/watchdog-survival-mode-sticky-until-stable.assertions.json env WATCHDOG_ENABLE_CONVERSATION_PROBE=true bash rehearsal/scripts/run-survival-sticky-flow.sh "$ENV_FILE"
    ;;
  watchdog-survival-mode-exit)
    run_json "$SCENARIO" 0 rehearsal/scenarios/watchdog-survival-mode-exit.assertions.json env WATCHDOG_ENABLE_CONVERSATION_PROBE=true bash rehearsal/scripts/run-survival-exit-flow.sh "$ENV_FILE"
    ;;
  watchdog-config-drift-guard)
    run_json "$SCENARIO" 0 rehearsal/scenarios/watchdog-config-drift-guard.assertions.json env WATCHDOG_ENABLE_CONVERSATION_PROBE=true WATCHDOG_ENABLE_SURVIVABILITY_FLOW=true WATCHDOG_ENABLE_SURVIVAL_MODE=true bash rehearsal/scripts/run-survivability-flow.sh "$SCENARIO" "$ENV_FILE"
    ;;
  watchdog-env-drift-rollback)
    run_json "$SCENARIO" 0 rehearsal/scenarios/watchdog-env-drift-rollback.assertions.json env WATCHDOG_ENABLE_CONVERSATION_PROBE=true bash rehearsal/scripts/run-drift-protected-flow.sh env "$ENV_FILE"
    ;;
  watchdog-plugin-drift-rollback)
    run_json "$SCENARIO" 0 rehearsal/scenarios/watchdog-plugin-drift-rollback.assertions.json env WATCHDOG_ENABLE_CONVERSATION_PROBE=true bash rehearsal/scripts/run-drift-protected-flow.sh plugin "$ENV_FILE"
    ;;
  watchdog-recovery-notify-normal)
    run_json "$SCENARIO" 0 rehearsal/scenarios/watchdog-recovery-notify-normal.assertions.json env WATCHDOG_ENABLE_CONVERSATION_PROBE=true WATCHDOG_ENABLE_SURVIVABILITY_FLOW=true bash rehearsal/scripts/run-survivability-flow.sh "$SCENARIO" "$ENV_FILE"
    ;;
  watchdog-last-good-generation-selection)
    run_json "$SCENARIO" 0 rehearsal/scenarios/watchdog-last-good-generation-selection.assertions.json env WATCHDOG_ENABLE_CONVERSATION_PROBE=true WATCHDOG_ENABLE_SURVIVABILITY_FLOW=true bash rehearsal/scripts/run-survivability-flow.sh "$SCENARIO" "$ENV_FILE"
    ;;
  watchdog-config-invalid-rollback)
    run_json "$SCENARIO" 0 rehearsal/scenarios/watchdog-config-invalid-rollback.assertions.json scripts/openclaw-watchdog --env "$ENV_FILE" run-once --json
    ;;
  watchdog-incidents-open)
    run_json "$SCENARIO" 0 rehearsal/scenarios/watchdog-incidents-open.assertions.json bash rehearsal/scripts/run-incident-flow.sh open "$ENV_FILE"
    ;;
  watchdog-incidents-resolved)
    run_json "$SCENARIO" 0 rehearsal/scenarios/watchdog-incidents-resolved.assertions.json bash rehearsal/scripts/run-incident-flow.sh resolved "$ENV_FILE"
    ;;
  watchdog-metrics-healthy)
    run_json "$SCENARIO" 0 rehearsal/scenarios/watchdog-metrics-healthy.assertions.json bash rehearsal/scripts/run-metrics-flow.sh healthy "$ENV_FILE"
    ;;
  watchdog-metrics-open-incident)
    run_json "$SCENARIO" 0 rehearsal/scenarios/watchdog-metrics-open-incident.assertions.json bash rehearsal/scripts/run-metrics-flow.sh open "$ENV_FILE"
    ;;
  watchdog-metrics-resolved)
    run_json "$SCENARIO" 0 rehearsal/scenarios/watchdog-metrics-resolved.assertions.json bash rehearsal/scripts/run-metrics-flow.sh resolved "$ENV_FILE"
    ;;
  watchdog-metrics-operator-context)
    run_json "$SCENARIO" 0 rehearsal/scenarios/watchdog-metrics-operator-context.assertions.json bash rehearsal/scripts/run-metrics-flow.sh operator-open "$ENV_FILE"
    ;;
  watchdog-report-operator-attention)
    run_json "$SCENARIO" 0 rehearsal/scenarios/watchdog-report-operator-attention.assertions.json bash rehearsal/scripts/run-report-attention-flow.sh open-unowned "$ENV_FILE"
    ;;
  watchdog-report-operator-attention-cleared)
    run_json "$SCENARIO" 0 rehearsal/scenarios/watchdog-report-operator-attention-cleared.assertions.json bash rehearsal/scripts/run-report-attention-flow.sh open-owned "$ENV_FILE"
    ;;
  watchdog-incident-attention-filter)
    run_json "$SCENARIO" 0 rehearsal/scenarios/watchdog-incident-attention-filter.assertions.json bash rehearsal/scripts/run-incident-attention-flow.sh "$ENV_FILE"
    ;;
  watchdog-incident-queue)
    run_json "$SCENARIO" 0 rehearsal/scenarios/watchdog-incident-queue.assertions.json bash rehearsal/scripts/run-incident-queue-flow.sh "$ENV_FILE"
    ;;
  watchdog-incident-operator-open)
    run_json "$SCENARIO" 0 rehearsal/scenarios/watchdog-incident-operator-open.assertions.json bash rehearsal/scripts/run-incident-operator-flow.sh open "$ENV_FILE"
    ;;
  watchdog-incident-operator-resolved)
    run_json "$SCENARIO" 0 rehearsal/scenarios/watchdog-incident-operator-resolved.assertions.json bash rehearsal/scripts/run-incident-operator-flow.sh resolved "$ENV_FILE"
    ;;
  watchdog-incident-operator-reset)
    run_json "$SCENARIO" 0 rehearsal/scenarios/watchdog-incident-operator-reset.assertions.json bash rehearsal/scripts/run-incident-operator-reset-flow.sh "$ENV_FILE"
    ;;
  watchdog-incident-timeline-open)
    run_json "$SCENARIO" 0 rehearsal/scenarios/watchdog-incident-timeline-open.assertions.json bash rehearsal/scripts/run-incident-timeline-flow.sh open "$ENV_FILE"
    ;;
  watchdog-incident-timeline-resolved)
    run_json "$SCENARIO" 0 rehearsal/scenarios/watchdog-incident-timeline-resolved.assertions.json bash rehearsal/scripts/run-incident-timeline-flow.sh resolved "$ENV_FILE"
    ;;
  watchdog-incident-notes-query)
    run_json "$SCENARIO" 0 rehearsal/scenarios/watchdog-incident-notes-query.assertions.json bash rehearsal/scripts/run-incident-notes-query-flow.sh "$ENV_FILE"
    ;;
  all)
    rehearsal/scripts/run-scenario.sh bootstrap-missing-openclaw
    rehearsal/scripts/run-scenario.sh bootstrap-openclaw-missing-plugin
    rehearsal/scripts/run-scenario.sh bootstrap-install-openclaw
    rehearsal/scripts/run-scenario.sh watchdog-recovery
    rehearsal/scripts/run-scenario.sh watchdog-failed-fallback
    rehearsal/scripts/run-scenario.sh watchdog-active-no-listener-grace
    rehearsal/scripts/run-scenario.sh watchdog-service-layer-degraded
    rehearsal/scripts/run-scenario.sh watchdog-service-layer-threshold-recovery
    rehearsal/scripts/run-scenario.sh watchdog-service-layer-transient-retry
    rehearsal/scripts/run-scenario.sh watchdog-conversation-probe-ready
    rehearsal/scripts/run-scenario.sh watchdog-conversation-probe-minimal
    rehearsal/scripts/run-scenario.sh watchdog-conversation-probe-down
    rehearsal/scripts/run-scenario.sh watchdog-restart-priority-recovery
    rehearsal/scripts/run-scenario.sh watchdog-rollback-priority-before-doctor
    rehearsal/scripts/run-scenario.sh watchdog-doctor-deferred-until-survival-fails
    rehearsal/scripts/run-scenario.sh watchdog-survival-mode-recovery
    rehearsal/scripts/run-scenario.sh watchdog-survival-mode-sticky-until-stable
    rehearsal/scripts/run-scenario.sh watchdog-survival-mode-exit
    rehearsal/scripts/run-scenario.sh watchdog-config-drift-guard
    rehearsal/scripts/run-scenario.sh watchdog-env-drift-rollback
    rehearsal/scripts/run-scenario.sh watchdog-plugin-drift-rollback
    rehearsal/scripts/run-scenario.sh watchdog-recovery-notify-normal
    rehearsal/scripts/run-scenario.sh watchdog-last-good-generation-selection
    rehearsal/scripts/run-scenario.sh watchdog-config-invalid-rollback
    rehearsal/scripts/run-scenario.sh watchdog-incidents-open
    rehearsal/scripts/run-scenario.sh watchdog-incidents-resolved
    rehearsal/scripts/run-scenario.sh watchdog-metrics-healthy
    rehearsal/scripts/run-scenario.sh watchdog-metrics-open-incident
    rehearsal/scripts/run-scenario.sh watchdog-metrics-resolved
    rehearsal/scripts/run-scenario.sh watchdog-metrics-operator-context
    rehearsal/scripts/run-scenario.sh watchdog-report-operator-attention
    rehearsal/scripts/run-scenario.sh watchdog-report-operator-attention-cleared
    rehearsal/scripts/run-scenario.sh watchdog-incident-attention-filter
    rehearsal/scripts/run-scenario.sh watchdog-incident-queue
    rehearsal/scripts/run-scenario.sh watchdog-incident-operator-open
    rehearsal/scripts/run-scenario.sh watchdog-incident-operator-resolved
    rehearsal/scripts/run-scenario.sh watchdog-incident-operator-reset
    rehearsal/scripts/run-scenario.sh watchdog-incident-timeline-open
    rehearsal/scripts/run-scenario.sh watchdog-incident-timeline-resolved
    rehearsal/scripts/run-scenario.sh watchdog-incident-notes-query
    ;;
  *)
    echo "Unknown scenario: $SCENARIO" >&2
    exit 1
    ;;
esac
