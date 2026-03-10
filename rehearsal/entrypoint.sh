#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

cd "$REPO_ROOT"
export PYTHONPATH="$REPO_ROOT${PYTHONPATH:+:$PYTHONPATH}"
export HOME="$REPO_ROOT/rehearsal/runtime/home"
bash rehearsal/scripts/prepare-system-bin.sh >/dev/null
export PATH="$REPO_ROOT/rehearsal/bin:$REPO_ROOT/rehearsal/runtime/bin:$REPO_ROOT/rehearsal/system-bin"

if [[ -f rehearsal/env/openclaw-watchdog.rehearsal.env ]]; then
  set -a
  source rehearsal/env/openclaw-watchdog.rehearsal.env
  set +a
fi

mkdir -p rehearsal/runtime/bin rehearsal/runtime/home

if [[ $# -eq 0 ]]; then
  exec bash
fi

case "$1" in
  shell|bash)
    shift || true
    exec bash "$@"
    ;;
  scenario)
    shift || true
    exec rehearsal/scripts/run-scenario.sh "$@"
    ;;
  reset-runtime)
    shift || true
    exec rehearsal/scripts/reset-runtime.sh "$@"
    ;;
  apply-scenario)
    shift || true
    exec rehearsal/scripts/apply-scenario.sh "$@"
    ;;
  bootstrap|provision|run-once|check|status|maintenance)
    exec scripts/openclaw-watchdog --env rehearsal/env/openclaw-watchdog.rehearsal.env "$@"
    ;;
  *)
    exec "$@"
    ;;
esac

