# Security Policy

## Supported scope

This repository is intended to contain only the sanitized watchdog project:

- watchdog engine code
- CLI wrappers
- sample systemd units
- docs and rehearsal assets

It should **not** contain:

- real `.env` files
- live incident bundles
- production status dumps
- host-specific secrets or tokens
- personal identifiers from operator channels

## Reporting a vulnerability

If you find a vulnerability or a repository leak:

1. Please avoid opening a public issue with secret material.
2. Report the issue privately to the repository owner.
3. Include:
   - affected file(s) or path(s)
   - impact summary
   - reproduction steps when safe
   - suggested mitigation, if available

## Repository hygiene

Before publishing or opening a PR, double-check that you are not including:

- OpenClaw tokens
- Feishu / QQ credentials
- GitHub tokens
- real incident artifacts
- operator notes copied from production
- hostnames, IPs, or open IDs that should stay private

## Operational warning

This project includes watchdog and repair automation. Review all configuration carefully before using it on a production system.
