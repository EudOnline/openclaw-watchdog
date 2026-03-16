# macOS Release-Grade Support Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Promote the current experimental macOS `launchd` path into a narrow, release-gated supported path for real macOS hosts without widening the product into a generic multi-platform framework.

**Architecture:** Because this project has not been deployed yet and backward compatibility is explicitly not required, this plan takes a scope-tightening approach rather than a compatibility-layer approach. Keep the existing platform-adapter seams, define one supported macOS shape (`LaunchAgent` in `gui/$UID`), make the env/config and live-acceptance path match that shape, and add release evidence plus CI gates around it. Do not add `LaunchDaemon`, system-wide service management, or a generic Darwin abstraction in this batch.

**Tech Stack:** Python 3.11 and 3.13, stdlib `unittest`, GitHub Actions, repo-local shell scripts, `launchctl`, `lsof`, `ps`, existing `openclaw_watchdog/platforms` adapters, existing `docs/p7a-live/` evidence flow.

---

## Scope and non-goals

This plan intentionally supports one macOS deployment shape only:

- user-session `LaunchAgent`
- label resolved as `gui/$UID/<launchd-label>`
- OpenClaw already installed on the target host
- watchdog configured from a repo-local env file

This plan does **not** include:

- `LaunchDaemon` support
- system-wide boot-without-login guarantees
- Windows support
- automatic installation of OpenClaw or rescue executors
- compatibility shims for legacy undeployed layouts

## Why this is the shortest correct path

The repo already has the essential seams:

- `openclaw_watchdog/platforms/macos_launchd.py`
- `scripts/install-openclaw-watchdog-launchd.sh`
- `launchd/com.eudonline.openclaw-watchdog.plist`
- focused tests for resolver and `launchd` adapter behavior

What is still missing is release discipline:

- the supported macOS shape is not defined tightly enough in docs
- the macOS env surface is not first-class
- CI does not yet prove the code on `macos-latest`
- live acceptance does not yet capture `launchd` host evidence
- the release gate still treats macOS as best-effort only

Fix those gaps in order instead of doing more architecture work.

## Exit criteria

Treat macOS as a supported release path only when all of these are true:

1. docs define the supported macOS shape as `LaunchAgent` + `gui/$UID`
2. the repo ships a macOS-specific env example that sets the gateway label explicitly
3. CI runs a macOS verification job and keeps it green
4. live acceptance can capture watchdog plus gateway `launchctl` evidence on a real macOS host
5. one real-host macOS acceptance pass is archived and summarized in release docs

## Task 1: Lock the supported macOS contract in docs

**Files:**
- Create: `docs/macos-launchd-rollout.md`
- Modify: `README.md`
- Modify: `docs/supported-environments.md`
- Modify: `docs/first-deployment.md`
- Modify: `docs/release-readiness.md`
- Test: `tests/test_docs_surface.py`

**Step 1: Write the failing docs test**

Add a focused test proving the public contract is now narrow and explicit:

```python
def test_docs_define_narrow_macos_launchagent_contract(self) -> None:
    readme_text = Path("README.md").read_text(encoding="utf-8")
    supported_text = Path("docs/supported-environments.md").read_text(encoding="utf-8")
    rollout_text = Path("docs/macos-launchd-rollout.md").read_text(encoding="utf-8")

    self.assertIn("LaunchAgent", rollout_text)
    self.assertIn("gui/$UID", rollout_text)
    self.assertIn("LaunchDaemon is out of scope", rollout_text)
    self.assertIn("macOS launchd rollout guide", readme_text)
    self.assertIn("supported macOS path", supported_text)
```

**Step 2: Run the test to verify it fails**

Run:

```bash
python3.13 -m unittest tests.test_docs_surface -v
```

Expected: FAIL because `docs/macos-launchd-rollout.md` does not exist yet and the current docs still describe macOS as experimental only.

**Step 3: Write the minimal docs implementation**

Create `docs/macos-launchd-rollout.md` and update the public docs so they all say the same thing:

- the supported macOS path is a user-session `LaunchAgent`
- the target namespace is `gui/$UID`
- the watchdog agent label is `com.eudonline.openclaw-watchdog`
- the gateway service label must be a macOS `launchd` label, not a Linux `.service` unit name
- `LaunchDaemon` is intentionally out of scope for this release batch

Use wording like this in the new doc:

```md
## Supported macOS shape

The supported macOS rollout target is a per-user LaunchAgent running in `gui/$UID`.
This batch does not support LaunchDaemon or system-wide service management.
Set `OPENCLAW_GATEWAY_SERVICE` to the launchd label used by the local OpenClaw gateway, for example `com.openclaw.gateway`.
```

Also update:

- `README.md` quick links and status text
- `docs/supported-environments.md` support-tier wording
- `docs/first-deployment.md` to link to the mac rollout guide
- `docs/release-readiness.md` so the future mac gate is named explicitly

**Step 4: Run the docs test again**

Run:

```bash
python3.13 -m unittest tests.test_docs_surface -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add README.md docs/macos-launchd-rollout.md docs/supported-environments.md docs/first-deployment.md docs/release-readiness.md tests/test_docs_surface.py
git commit -m "docs: define narrow macos launchd support contract"
```

## Task 2: Make the macOS env surface first-class

**Files:**
- Create: `config/openclaw-watchdog.macos.env.example`
- Modify: `README.md`
- Modify: `docs/macos-launchd-rollout.md`
- Modify: `docs/first-deployment.md`
- Test: `tests/test_docs_surface.py`

**Step 1: Write the failing surface test**

Add a docs/surface assertion that the repo ships a macOS example env and that it sets a `launchd`-style gateway label:

```python
def test_repo_ships_macos_env_example(self) -> None:
    env_text = Path("config/openclaw-watchdog.macos.env.example").read_text(encoding="utf-8")
    self.assertIn("OPENCLAW_GATEWAY_SERVICE=com.openclaw.gateway", env_text)
    self.assertIn("WATCHDOG_STATE_DIR=", env_text)
```

**Step 2: Run the test to verify it fails**

Run:

```bash
python3.13 -m unittest tests.test_docs_surface -v
```

Expected: FAIL because the macOS env example file is missing.

**Step 3: Write the minimal implementation**

Create `config/openclaw-watchdog.macos.env.example` by starting from the current sanitized env defaults and overriding only the mac-specific values:

```dotenv
OPENCLAW_GATEWAY_SERVICE=com.openclaw.gateway
WATCHDOG_STATE_DIR=~/.openclaw-backup/watchdog
WATCHDOG_LOG_FILE=~/.openclaw-backup/watchdog/watchdog.log
WATCHDOG_LAST_REPORT_FILE=~/.openclaw-backup/watchdog/last-report.json
WATCHDOG_LAST_METRICS_FILE=~/.openclaw-backup/watchdog/last-metrics.json
```

Document one operator flow only:

```bash
cp config/openclaw-watchdog.macos.env.example config/openclaw-watchdog.env
scripts/install-openclaw-watchdog-launchd.sh
```

Do not fork runtime behavior between Linux and macOS; only fork the example env and docs.

**Step 4: Run the test again**

Run:

```bash
python3.13 -m unittest tests.test_docs_surface -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add config/openclaw-watchdog.macos.env.example README.md docs/macos-launchd-rollout.md docs/first-deployment.md tests/test_docs_surface.py
git commit -m "docs: add macos env example for launchd path"
```

## Task 3: Harden the macOS adapter and add a macOS CI gate

**Files:**
- Modify: `openclaw_watchdog/platforms/macos_launchd.py`
- Modify: `tests/test_macos_launchd_adapter.py`
- Modify: `tests/test_platform_resolver.py`
- Modify: `.github/workflows/ci.yml`
- Modify: `tests/test_ci_contract.py`

**Step 1: Write the failing tests**

Add targeted adapter tests for the unhappy paths that matter on a real host:

```python
def test_describe_service_returns_empty_info_when_launchctl_has_no_parseable_fields(self) -> None:
    engine = MacosLaunchdEngineDouble()
    engine._responses[("launchctl", "print", "gui/501/com.openclaw.gateway")] = _result(
        ["launchctl"],
        returncode=113,
        stdout="Could not find service",
    )
    adapter = MacosLaunchdPlatform(uid=501)
    self.assertEqual(adapter.describe_service(engine), {})

def test_restart_service_logs_warning_when_kickstart_fails(self) -> None:
    engine = MacosLaunchdEngineDouble()
    engine._responses[("launchctl", "kickstart", "-k", "gui/501/com.openclaw.gateway")] = _result(
        ["launchctl"],
        returncode=1,
        stderr="service already bootstrapped",
    )
    adapter = MacosLaunchdPlatform(uid=501)
    self.assertFalse(adapter.restart_service(engine))
    self.assertEqual(engine.logs[-1][0], "WARN")
```

Add a CI contract test that proves the workflow contains a macOS job:

```python
def test_ci_workflow_includes_macos_verification_job(self) -> None:
    workflow_text = Path(".github/workflows/ci.yml").read_text(encoding="utf-8")
    self.assertIn("macos-latest", workflow_text)
    self.assertIn("tests/test_macos_launchd_adapter.py", workflow_text)
```

**Step 2: Run the targeted tests to verify they fail**

Run:

```bash
python3.13 -m unittest tests.test_macos_launchd_adapter tests.test_ci_contract -v
```

Expected: FAIL because the new tests and workflow assertions are not implemented yet.

**Step 3: Write the minimal implementation**

Keep the code change narrow:

- retain `MacosLaunchdPlatform` as the single macOS adapter owner
- make parse failures return `{}` without raising
- keep restart failure logging explicit
- add a `macos-verify` CI job on `macos-latest`
- run package install, console-script smoke, full `unittest`, and the focused macOS adapter tests on that job

Use a CI shape like:

```yaml
  macos-verify:
    runs-on: macos-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.13'
      - run: python -m pip install .
      - run: openclaw-watchdog --help
      - run: python -m unittest tests/test_macos_launchd_adapter.py tests/test_platform_resolver.py -v
      - run: python -m unittest discover -s tests -v
```

Keep `critical` rehearsal on Ubuntu only in this batch.

**Step 4: Run the targeted tests and then the repo gate**

Run:

```bash
python3.13 -m unittest tests.test_macos_launchd_adapter tests.test_platform_resolver tests.test_ci_contract -v
python3.13 -m unittest discover -s tests -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add openclaw_watchdog/platforms/macos_launchd.py tests/test_macos_launchd_adapter.py tests/test_platform_resolver.py .github/workflows/ci.yml tests/test_ci_contract.py
git commit -m "ci: add macos gate and harden launchd adapter"
```

## Task 4: Make live acceptance env-aware and capture macOS supervisor evidence

**Files:**
- Modify: `scripts/openclaw-watchdog-live-acceptance.sh`
- Create: `tests/test_live_acceptance_contract.py`
- Modify: `docs/live-acceptance-checklist.md`
- Modify: `docs/macos-launchd-rollout.md`
- Modify: `docs/release-readiness.md`

**Step 1: Write the failing contract test**

Create a new contract test for the live-acceptance script surface:

```python
def test_live_acceptance_script_supports_env_and_macos_launchd_evidence(self) -> None:
    script = Path("scripts/openclaw-watchdog-live-acceptance.sh").read_text(encoding="utf-8")
    self.assertIn("--env", script)
    self.assertIn("launchctl print", script)
    self.assertIn("watchdog-launchd.txt", script)
    self.assertIn("gateway-launchd.txt", script)
```

**Step 2: Run the test to verify it fails**

Run:

```bash
python3.13 -m unittest tests.test_live_acceptance_contract -v
```

Expected: FAIL because the script is not yet env-aware and does not capture `launchd` evidence.

**Step 3: Write the minimal implementation**

Upgrade the existing script instead of adding a second acceptance entrypoint:

1. parse `--env <path>` and `--out-dir <path>`
2. pass `--env` through to all watchdog CLI calls
3. load the config in a small Python snippet and derive:
   - resolved env file
   - platform host family
   - supervisor type
   - configured gateway label
4. when the resolved platform is macOS + `launchd`, capture:
   - `launchctl print gui/$UID/com.eudonline.openclaw-watchdog` to `watchdog-launchd.txt`
   - `launchctl print gui/$UID/<OPENCLAW_GATEWAY_SERVICE>` to `gateway-launchd.txt`
5. include those file names and checks in the acceptance summary when the host is macOS

Use a shell shape like:

```bash
ENV_FILE=""
OUT_DIR="docs/p7a-live"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --env) ENV_FILE="$2"; shift 2 ;;
    --out-dir) OUT_DIR="$2"; shift 2 ;;
    *) echo "unknown arg: $1" >&2; exit 2 ;;
  esac
done
```

And a Python helper shape like:

```python
from pathlib import Path
from openclaw_watchdog.config import Config
from openclaw_watchdog.platforms.resolver import resolve_platform

config = Config.load(Path(env_file) if env_file else None)
platform = resolve_platform()
print(json.dumps({
    "host_family": platform.capabilities.host_family,
    "supervisor": platform.capabilities.supervisor,
    "gateway_service": config.openclaw_gateway_service,
}))
```

**Step 4: Run the new contract test and the full suite**

Run:

```bash
python3.13 -m unittest tests.test_live_acceptance_contract -v
python3.13 -m unittest discover -s tests -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add scripts/openclaw-watchdog-live-acceptance.sh tests/test_live_acceptance_contract.py docs/live-acceptance-checklist.md docs/macos-launchd-rollout.md docs/release-readiness.md
git commit -m "feat: capture macos launchd evidence in live acceptance"
```

## Task 5: Capture the first real-host macOS evidence and promote support status

**Files:**
- Modify: `README.md`
- Modify: `docs/supported-environments.md`
- Modify: `docs/release-readiness.md`
- Modify: `docs/release-notes-v0.2.0-draft.md`
- Modify: `CHANGELOG.md`
- Test: `tests/test_docs_surface.py`

**Step 1: Prepare a real macOS candidate host**

Run on the real host:

```bash
cp config/openclaw-watchdog.macos.env.example config/openclaw-watchdog.env
scripts/openclaw-watchdog detect
scripts/openclaw-watchdog check --env config/openclaw-watchdog.env
scripts/openclaw-watchdog status --env config/openclaw-watchdog.env --summary
scripts/openclaw-watchdog report --env config/openclaw-watchdog.env --message
scripts/install-openclaw-watchdog-launchd.sh
./scripts/openclaw-watchdog-live-acceptance.sh --env config/openclaw-watchdog.env --out-dir docs/p7a-live
```

Expected:

- `launchctl print gui/$UID/com.eudonline.openclaw-watchdog` succeeds
- `launchctl print gui/$UID/<gateway-label>` succeeds
- `docs/p7a-live/acceptance-summary.json` shows `"all_checks_passed": true`

**Step 2: Write the failing docs promotion test**

After the real-host evidence exists, add a test proving the public docs no longer call the supported macOS path experimental:

```python
def test_docs_promote_macos_after_real_host_evidence(self) -> None:
    readme_text = Path("README.md").read_text(encoding="utf-8")
    supported_text = Path("docs/supported-environments.md").read_text(encoding="utf-8")

    self.assertIn("macOS + launchd LaunchAgent", readme_text)
    self.assertIn("supported production path", supported_text)
    self.assertNotIn("experimental macOS + launchd path", supported_text)
```

**Step 3: Run the test to verify it fails**

Run:

```bash
python3.13 -m unittest tests.test_docs_surface -v
```

Expected: FAIL until the support-tier wording is updated.

**Step 4: Write the minimal promotion docs**

Update the public surfaces with the real, narrow promise:

- `README.md`: macOS `LaunchAgent` support is available for the documented user-session path
- `docs/supported-environments.md`: list macOS `launchd` `LaunchAgent` as supported, but keep `LaunchDaemon` unsupported
- `docs/release-readiness.md`: require one archived macOS acceptance bundle before claiming macOS support in the release
- `docs/release-notes-v0.2.0-draft.md`: summarize the host evidence from `docs/p7a-live/`
- `CHANGELOG.md`: record that the macOS support claim changed because evidence was added

Do not promote support status before the host evidence exists.

**Step 5: Run the docs test and the full suite**

Run:

```bash
python3.13 -m unittest tests.test_docs_surface -v
python3.13 -m unittest discover -s tests -v
```

Expected: PASS.

**Step 6: Commit**

```bash
git add README.md docs/supported-environments.md docs/release-readiness.md docs/release-notes-v0.2.0-draft.md CHANGELOG.md tests/test_docs_surface.py
git commit -m "docs: promote macos launchd path after live evidence"
```

## Release checklist after the plan lands

Before tagging a release that claims macOS support, rerun this exact sequence:

```bash
python3.13 -m unittest discover -s tests -v
bash rehearsal/scripts/run-scenario.sh critical
./scripts/openclaw-watchdog-live-acceptance.sh --env config/openclaw-watchdog.env --out-dir docs/p7a-live
```

Ship only if:

- the repo-local suite is green
- the critical rehearsal tier is green
- the macOS host acceptance bundle is green
- docs and release notes match the evidence

## Recommended order of execution

1. Task 1
2. Task 2
3. Task 3
4. Task 4
5. Task 5

This order matters. Do not promote support claims before the env surface, CI gate, and host evidence path exist.
