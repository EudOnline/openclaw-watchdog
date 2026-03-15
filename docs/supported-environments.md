# Supported environments

This document defines the environments that the OpenClaw fallback system currently treats as part of its supported public surface.

## Support tiers

The OpenClaw fallback system distinguishes between three layers of support:

1. **Production-path support**: environments expected to run the watchdog against a real OpenClaw deployment.
2. **Repo-local rehearsal support**: environments expected to run the repo's deterministic rehearsal harness.
3. **Development and CI support**: environments used to validate code changes, contracts, and release quality gates.

If an environment is not listed below, it may still work, but it is not yet part of the promised release discipline.

## Production-path support

The current supported production baseline is:

- Python `3.11+`
- Linux
- `systemd --user`
- OpenClaw installed on the target machine
- Standard host tools used by the watchdog flows, such as `systemctl`, `ss`, `ps`, and `journalctl`
- any rescue CLI you expect the fallback chain to use (`Codex`, `Claude Code`, `Gemini CLI`, or `OpenCode`) already installed if you want that tier available
- a configured remote-model endpoint if you want the `LiteLLM` specialist agent to be available

This is the only environment family the sample systemd units, first-deployment guide, and unattended timer flow are designed around today. The fallback system does not install missing rescue executors, model clients, or OpenClaw automatically; support assumes required tools are already present and configured.

An **experimental** macOS + `launchd` adapter path now exists in the repository for architecture validation and local host testing. It is not yet part of the live-validated production baseline, and it should not be treated as a production-ready rollout path until it has explicit acceptance evidence and release-gated validation.

## Repo-local rehearsal support

The rehearsal harness is intended to be host-isolated and repo-local, but the release gate currently treats the following baseline as supported:

- Python `3.11+`
- POSIX shell environment
- ability to run the scripts under `rehearsal/scripts/`
- ability to execute the shipped shims and repo-local command wrappers
- optional access to a remote model endpoint when rehearsal coverage exercises the `LiteLLM` rescue tier

The rehearsal harness does **not** require a real OpenClaw deployment, but it still depends on a compatible Python interpreter and standard shell tooling.

GitHub Actions on Ubuntu is the canonical release-gated rehearsal environment. Other hosts may work for local development, but they are currently best-effort unless they match the same constraints.

## Development and CI support

The current maintained validation path is:

- Python `3.11` and `3.13` in CI for CLI, contract, and rehearsal coverage
- focused `unittest` coverage for contracts and helper modules
- repo-local rehearsal scenarios for product-defining flows
- byte-compilation checks for the shipped Python modules and tests

At minimum, release validation should continue to cover:

- `python -m openclaw_watchdog --help`
- `python -m unittest tests/test_cli_smoke.py -v`
- `python -m unittest discover -s tests -v`
- `python -m py_compile openclaw_watchdog/*.py rehearsal/lib/*.py rehearsal/tools/*.py tests/*.py`
- bounded rehearsal scenarios that represent conversation readiness, remediation failure, incident workflow behavior, and rescue-chain selection

The current critical rehearsal gate should continue to protect the product-defining survivability path, including:

- rescue-chain selection across the canonical executor order
- conversation-aware readiness probes
- rollback before doctor repair
- survival-mode recovery
- config-drift rollback protection

## Explicitly unsupported today

These environments are not currently part of the promised public support surface:

- Python `3.10` and below
- Windows production deployment
- non-`systemd` service supervision paths as a first-class documented deployment target
- hosts that require the watchdog to manage a live gateway without the documented Linux user-service assumptions
- generic multi-product watchdog use outside OpenClaw
- hosts that require automatic installation of rescue tools or model clients

Experimental macOS `launchd` support sits between supported and unsupported: the adapter and install assets exist, but the path is still best-effort until live acceptance and release discipline are added for it.

Unsupported does not necessarily mean impossible. It means changes are not release-gated against those environments, and behavior there may change without a compatibility promise.

## Release discipline

When changing code, docs, or examples that touch compatibility:

1. keep the Python `3.11+` requirement explicit;
2. avoid broadening support claims without adding validation to CI or rehearsal coverage;
3. update this document, `README.md`, and `docs/history/migration-legacy-rollout.md` when the public support surface changes;
4. record compatibility-impacting changes in `CHANGELOG.md`;
5. call out unsupported or best-effort paths clearly in PR descriptions.

Internal refactors are encouraged when they reduce maintenance risk, but they should preserve the documented CLI entrypoints, stable report/metrics outputs, fixed rescue-chain order, and rehearsal scenario intent unless an explicit migration note says otherwise.

For release preparation, use [release-readiness.md](release-readiness.md) as the operator-maintainer checklist. The current planned next release is `v0.2.0`, and that gate should remain grounded in Python `3.11+`, repo-local validation, critical rehearsal coverage, and live acceptance on a real Linux + `systemd --user` host.

## Practical guidance

- New operators should follow `docs/first-deployment.md` and assume the Linux + `systemd --user` path unless the docs explicitly say otherwise.
- Contributors validating host abstractions can use the experimental macOS `launchd` assets, but they should describe that path as experimental until the support tier changes.
- Contributors should treat repo-local rehearsal as the preferred way to validate behavior before relying on a live host.
- Maintainers preparing a release should assemble evidence in the order documented by `docs/release-readiness.md`.
- If your local machine cannot run Python `3.11+`, you can still edit docs or some tests, but release-gated CLI and rehearsal checks must run in CI or on a compatible host.
