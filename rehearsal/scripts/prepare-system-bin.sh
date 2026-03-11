#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(/usr/bin/dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
BIN_DIR="$REPO_ROOT/rehearsal/runtime/system-bin"

/bin/mkdir -p "$BIN_DIR"

for cmd in bash env python3 python3.11 python3.12 python3.13 timeout script diff cat cp ln mkdir rm touch sleep dirname head tail sed grep awk sort uniq wc nohup ls find git sh; do
  real=""
  for base in /opt/homebrew/bin /usr/local/bin /Library/Developer/CommandLineTools/usr/bin /usr/bin /bin; do
    if [[ -x "$base/$cmd" ]]; then
      real="$base/$cmd"
      break
    fi
  done
  if [[ -n "$real" ]]; then
    /bin/ln -sf "$real" "$BIN_DIR/$cmd"
  fi
done
