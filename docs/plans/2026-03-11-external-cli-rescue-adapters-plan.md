# External CLI Rescue Adapters Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make `Codex`, `Claude Code`, `Gemini CLI`, and `OpenCode` adapters return validated structured rescue plans instead of acting as inert availability markers.

**Architecture:** Introduce one shared CLI adapter base that builds a strict rescue prompt, invokes a binary, extracts a JSON object from stdout, and validates it through `RescuePlan.from_dict()`. Keep each provider-specific adapter thin: only name, command, and prompt flavor differ. Dispatcher behavior stays unchanged because all external CLIs converge to the same `RescuePlan` interface.

**Tech Stack:** Python 3.13, stdlib `json`/`subprocess` helpers already exposed via engine runtime, existing rescue models and dispatcher tests.

---

### Task 1: Add failing tests for structured CLI adapters
- Cover JSON extraction, refusal of free-form shell payloads, and provider order.
- Verify unavailable adapters still skip cleanly.

### Task 2: Build shared strict CLI adapter base
- Add prompt builder, stdout JSON extractor, timeout handling, and structured validation.
- Reject non-JSON output and shell-like payloads.

### Task 3: Rewire provider adapters onto the shared base
- `codex`, `claude-code`, `gemini-cli`, `opencode` each declare binary + provider label only.
- Preserve existing names for dispatcher ordering.

### Task 4: Wire engine/runtime integration
- Let adapters call through engine `run_command` instead of raw subprocess logic.
- Keep no-install and no-arbitrary-shell guarantees.

### Task 5: Verify focused suites
- Run adapter and dispatcher tests.
- Run byte-compile on changed modules.
