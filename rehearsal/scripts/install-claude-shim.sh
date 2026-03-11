#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

mkdir -p "$REPO_ROOT/rehearsal/runtime/bin"
ln -sf "$REPO_ROOT/rehearsal/shims/claude" "$REPO_ROOT/rehearsal/runtime/bin/claude"
ln -sf "$REPO_ROOT/rehearsal/shims/claude" "$REPO_ROOT/rehearsal/runtime/bin/claude-code"
echo "Installed Claude rehearsal shim at rehearsal/runtime/bin/claude"
