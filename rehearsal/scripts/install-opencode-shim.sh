#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

mkdir -p "$REPO_ROOT/rehearsal/runtime/bin"
ln -sf "$REPO_ROOT/rehearsal/shims/opencode" "$REPO_ROOT/rehearsal/runtime/bin/opencode"
echo "Installed OpenCode rehearsal shim at rehearsal/runtime/bin/opencode"

