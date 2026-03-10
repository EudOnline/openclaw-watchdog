#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
BIN_DIR="$REPO_ROOT/rehearsal/system-bin"

mkdir -p "$BIN_DIR"

for cmd in bash env python3 timeout script diff cat cp ln mkdir rm touch sleep dirname head tail sed grep awk sort uniq wc nohup ls find git sh; do
  real=""
  for base in /usr/bin /bin /usr/local/bin; do
    if [[ -x "$base/$cmd" ]]; then
      real="$base/$cmd"
      break
    fi
  done
  if [[ -n "$real" ]]; then
    ln -sf "$real" "$BIN_DIR/$cmd"
  fi
done
