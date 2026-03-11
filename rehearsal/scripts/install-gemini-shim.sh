#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

mkdir -p "$REPO_ROOT/rehearsal/runtime/bin"
ln -sf "$REPO_ROOT/rehearsal/shims/gemini" "$REPO_ROOT/rehearsal/runtime/bin/gemini"
ln -sf "$REPO_ROOT/rehearsal/shims/gemini" "$REPO_ROOT/rehearsal/runtime/bin/gemini-cli"
echo "Installed Gemini rehearsal shim at rehearsal/runtime/bin/gemini"
