#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT_DIR="${SCOUT_OUTPUT_DIR:-$ROOT_DIR/.tmp/openclaw-upstream-scout}"

mkdir -p "$OUT_DIR"

write_metadata() {
  local key="$1"
  local value="$2"
  printf '%s=%s\n' "$key" "$value" >>"$OUT_DIR/metadata.env"
}

run_capture() {
  local stem="$1"
  shift

  local output_file="$OUT_DIR/${stem}.txt"
  local rc_file="$OUT_DIR/${stem}.rc"
  local rc=0

  if "$@" >"$output_file" 2>&1; then
    rc=0
  else
    rc=$?
  fi

  printf '%s\n' "$rc" >"$rc_file"
  return 0
}

summarize_json_keys() {
  local input_file="$1"
  local output_file="$2"

  if ! command -v python3 >/dev/null 2>&1; then
    printf 'python3-unavailable\n' >"$output_file"
    return 0
  fi

  python3 - "$input_file" "$output_file" <<'PY'
import json
import pathlib
import sys

input_path = pathlib.Path(sys.argv[1])
output_path = pathlib.Path(sys.argv[2])
text = input_path.read_text(encoding="utf-8", errors="replace").strip()
decoder = json.JSONDecoder()
payload = None

for index, char in enumerate(text):
    if char != "{":
        continue
    try:
        payload, _ = decoder.raw_decode(text[index:])
    except json.JSONDecodeError:
        continue
    if isinstance(payload, dict):
        break

if isinstance(payload, dict):
    output_path.write_text("\n".join(sorted(payload.keys())) + "\n", encoding="utf-8")
else:
    output_path.write_text("unparseable\n", encoding="utf-8")
PY
}

: >"$OUT_DIR/metadata.env"
write_metadata "generated_at_utc" "$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
write_metadata "root_dir" "$ROOT_DIR"

if command -v openclaw >/dev/null 2>&1; then
  OPENCLAW_BIN="$(command -v openclaw)"
  write_metadata "openclaw_available" "true"
  write_metadata "openclaw_binary" "$OPENCLAW_BIN"
else
  write_metadata "openclaw_available" "false"
  write_metadata "openclaw_binary" ""
  printf 'openclaw was not found on PATH\n' >"$OUT_DIR/openclaw-missing.txt"
  printf '%s\n' "$OUT_DIR"
  exit 0
fi

run_capture "openclaw-help" openclaw --help
run_capture "doctor-help" openclaw doctor --help
run_capture "status-json-raw" openclaw status --json --timeout 5000
run_capture "health-json-raw" openclaw health --json

summarize_json_keys "$OUT_DIR/status-json-raw.txt" "$OUT_DIR/status-json-top-level-keys.txt"
summarize_json_keys "$OUT_DIR/health-json-raw.txt" "$OUT_DIR/health-json-top-level-keys.txt"

printf '%s\n' "$OUT_DIR"
