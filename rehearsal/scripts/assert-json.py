#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from glob import glob
from pathlib import Path
from typing import Any


def lookup(payload: Any, dotted: str) -> Any:
    current = payload
    for part in dotted.split("."):
        if isinstance(current, list):
            current = current[int(part)]
            continue
        current = current[part]
    return current


def fail(message: str) -> int:
    print(message, file=sys.stderr)
    return 1


def main() -> int:
    if len(sys.argv) != 5:
        return fail("usage: assert-json.py <payload.json> <assertions.json> <actual-exit> <expected-exit>")

    payload = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    assertions = json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))
    actual_exit = int(sys.argv[3])
    expected_exit = int(sys.argv[4])

    if actual_exit != expected_exit:
        return fail(f"exit code mismatch: expected {expected_exit}, got {actual_exit}")

    for dotted, expected in assertions.get("equals", {}).items():
        actual = lookup(payload, dotted)
        if actual != expected:
            return fail(f"{dotted} mismatch: expected {expected!r}, got {actual!r}")

    for dotted, expected_substring in assertions.get("contains", {}).items():
        actual = str(lookup(payload, dotted))
        if expected_substring not in actual:
            return fail(f"{dotted} missing substring {expected_substring!r}: got {actual!r}")

    for dotted, unexpected_substring in assertions.get("not_contains", {}).items():
        actual = str(lookup(payload, dotted))
        if unexpected_substring in actual:
            return fail(f"{dotted} unexpectedly contains substring {unexpected_substring!r}: got {actual!r}")

    for dotted, expected_items in assertions.get("includes", {}).items():
        actual = lookup(payload, dotted)
        if not isinstance(actual, list):
            return fail(f"{dotted} is not a list")
        missing = [item for item in expected_items if item not in actual]
        if missing:
            return fail(f"{dotted} missing expected items: {missing!r}")

    for file_path, expected_substrings in assertions.get("file_contains", {}).items():
        actual = Path(file_path).read_text(encoding="utf-8")
        missing = [item for item in expected_substrings if item not in actual]
        if missing:
            return fail(f"file {file_path} missing expected substrings: {missing!r}")

    for file_path, unexpected_substrings in assertions.get("file_not_contains", {}).items():
        actual = Path(file_path).read_text(encoding="utf-8")
        present = [item for item in unexpected_substrings if item in actual]
        if present:
            return fail(f"file {file_path} unexpectedly contains substrings: {present!r}")

    for pattern, expected_substrings in assertions.get("glob_file_contains", {}).items():
        matches = sorted(glob(pattern))
        if not matches:
            return fail(f"glob matched no files: {pattern}")
        actual = Path(matches[-1]).read_text(encoding="utf-8")
        missing = [item for item in expected_substrings if item not in actual]
        if missing:
            return fail(f"file {matches[-1]} missing expected substrings: {missing!r}")

    for pattern, unexpected_substrings in assertions.get("glob_file_not_contains", {}).items():
        matches = sorted(glob(pattern))
        if not matches:
            return fail(f"glob matched no files: {pattern}")
        actual = Path(matches[-1]).read_text(encoding="utf-8")
        present = [item for item in unexpected_substrings if item in actual]
        if present:
            return fail(f"file {matches[-1]} unexpectedly contains substrings: {present!r}")

    print("assertions passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
