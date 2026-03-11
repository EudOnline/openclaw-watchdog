# Supported environments

This document defines the environments that OpenClaw Watchdog currently treats as part of its supported public surface.

## Support tiers

OpenClaw Watchdog distinguishes between three layers of support:

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

This is the only environment family the sample systemd units, first-deployment guide, and unattended timer flow are designed around today.

## Repo-local rehearsal support

The rehearsal harness is intended to be host-isolated and repo-local, but the release gate currently treats the following baseline as supported:

- Python `3.11+`
- POSIX shell environment
- ability to run the scripts under `rehearsal/scripts/`
- ability to execute the shipped shims and repo-local command wrappers

The rehearsal harness does **not** require a real OpenClaw deployment, but it still depends on a compatible Python interpreter and standard shell tooling.

GitHub Actions on Ubuntu is the canonical release-gated rehearsal environment. Other hosts may work for local development, but they are currently best-effort unless they match the same constraints.

## Development and CI support

The current maintained validation path is:

- Python `3.11+` in CI for CLI and rehearsal coverage
- focused `unittest` coverage for contracts and helper modules
- repo-local rehearsal scenarios for product-defining flows
- byte-compilation checks for the shipped Python modules and tests

At minimum, release validation should continue to cover:

- `python -m watchdog_v2 --help`
- `python -m unittest tests/test_cli_smoke.py -v`
- `python -m unittest discover -s tests -v`
- `python -m py_compile watchdog_v2/*.py rehearsal/lib/*.py rehearsal/tools/*.py tests/*.py`
- bounded rehearsal scenarios that represent conversation readiness, remediation failure, and incident workflow behavior

## Explicitly unsupported today

These environments are not currently part of the promised public support surface:

- Python `3.10` and below
- Windows production deployment
- non-`systemd` service supervision paths as a first-class documented deployment target
- hosts that require the watchdog to manage a live gateway without the documented Linux user-service assumptions

Unsupported does not necessarily mean impossible. It means changes are not release-gated against those environments, and behavior there may change without a compatibility promise.

## Release discipline

When changing code, docs, or examples that touch compatibility:

1. keep the Python `3.11+` requirement explicit;
2. avoid broadening support claims without adding validation to CI or rehearsal coverage;
3. update this document, `README.md`, and `docs/compatibility-and-deprecations.md` when the public support surface changes;
4. record compatibility-impacting changes in `CHANGELOG.md`;
5. call out unsupported or best-effort paths clearly in PR descriptions.

Internal refactors are encouraged when they reduce maintenance risk, but they should preserve the documented CLI entrypoints, stable report/metrics outputs, and rehearsal scenario intent unless an explicit migration note says otherwise.

## Practical guidance

- New operators should follow `docs/first-deployment.md` and assume the Linux + `systemd --user` path unless the docs explicitly say otherwise.
- Contributors should treat repo-local rehearsal as the preferred way to validate behavior before relying on a live host.
- If your local machine cannot run Python `3.11+`, you can still edit docs or some tests, but release-gated CLI and rehearsal checks must run in CI or on a compatible host.
