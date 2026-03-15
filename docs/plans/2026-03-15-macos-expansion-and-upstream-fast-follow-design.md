# macOS Expansion And Upstream Fast-Follow Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Restructure the watchdog so Linux becomes one host adapter instead of the architecture, macOS can be added without spreading platform conditionals through recovery logic, and fast-moving OpenClaw changes are absorbed inside narrow upstream contracts.

**Architecture:** Because this project has not been deployed yet and backward compatibility is explicitly not required, this plan takes an architecture-cut approach rather than a compatibility-layer approach. The core recovery flow stays OpenClaw-specific and deterministic, but host supervision, process inspection, listener discovery, and install/schedule behavior move behind platform adapters. OpenClaw CLI, status, config, and doctor semantics move behind a separate upstream adapter seam. Validation should favor capability detection and fixture-backed contract tests instead of version switches and one-off shims.

**Tech Stack:** Python 3.11 and 3.13, stdlib `unittest`, repo-local rehearsal harness, shell install helpers, GitHub Actions, existing `openclaw_watchdog` runtime owners.

---

## Current repo reality that motivates this cut

The current codebase already has a strong runtime core, but the host integration seam is still Linux-shaped:

- `openclaw_watchdog/service_runtime.py` directly calls `systemctl --user`, `ss`, and `ps`
- `openclaw_watchdog/repair_action_runtime.py` directly restarts the gateway through `systemctl --user`
- `openclaw_watchdog/detect_service_runtime.py` treats `systemctl --user show` as the canonical service probe
- `scripts/install-openclaw-watchdog-units.sh` assumes user-scoped `systemd`
- `docs/supported-environments.md` currently defines Linux + `systemd --user` as the only production path

That is still a manageable refactor surface. The Linux coupling is concentrated enough that the right move is to extract it cleanly now, before operators depend on it as a permanent contract.

## Approaches considered

### Option A: Clean architecture cut now

Create platform adapters and an OpenClaw upstream adapter, then make Linux + `systemd --user` one implementation of those contracts. Add macOS later as `launchd` without changing recovery semantics.

**Why this is recommended**

- no migration tax yet because nothing has been deployed
- avoids future `if darwin` spread through repair and detect flows
- gives OpenClaw fast-follow one narrow seam instead of many direct command assumptions
- lets rehearsal and CI validate contracts instead of host-specific incidental behavior

### Option B: Keep current Linux architecture and add macOS conditionals

Patch `service_runtime.py`, `repair_action_runtime.py`, and install scripts with platform branches.

**Why this is not recommended**

- fastest short-term path, but creates permanent entanglement
- every future OpenClaw change would still force edits across Linux/macOS branches
- testing grows combinatorially because behavior is mixed with host detection

### Option C: Build a generic plugin framework first

Create a highly abstract multi-product orchestration layer before adding macOS.

**Why this is not recommended**

- too much infrastructure for the problem at hand
- risks delaying real host extraction work
- this project is still intentionally OpenClaw-specific

Recommendation: choose **Option A** and treat the current Linux path as a temporary adapter implementation, not a public architectural promise.

## Target package shape

The package can stay OpenClaw-specific while still separating the host and upstream seams:

```text
openclaw_watchdog/
  platforms/
    __init__.py
    base.py
    capabilities.py
    resolver.py
    linux_systemd.py
    macos_launchd.py
  openclaw_runtime/
    __init__.py
    adapter.py
    capabilities.py
    contracts.py
    status_runtime.py
    config_runtime.py
    doctor_runtime.py
```

Keep the deterministic recovery order unchanged:

`restart -> rollback -> survival -> doctor -> rescue`

Only the implementations of `restart`, `listener inspection`, `service state lookup`, and OpenClaw contract parsing should move.

## Core contracts to introduce

### Platform seam

```python
@dataclass(frozen=True)
class PlatformCapabilities:
    host_family: str
    supervisor: str
    listener_tool: str
    supports_managed_restart: bool
    supports_listener_pid_tree: bool


class SupervisorAdapter(Protocol):
    def service_active(self, engine) -> bool: ...
    def service_main_pid(self, engine) -> str: ...
    def restart_service(self, engine) -> bool: ...
    def install_watchdog_schedule(self, engine) -> None: ...


class ListenerAdapter(Protocol):
    def listener_pids(self, engine) -> list[str]: ...
    def listener_contains_pid(self, engine, needle: str) -> bool: ...
    def listener_matches_service_tree(self, engine, main_pid: str) -> tuple[bool, str, str]: ...
```

### OpenClaw upstream seam

```python
@dataclass(frozen=True)
class GatewayContract:
    url: str
    reachable: bool
    misconfigured: bool
    configured_port: int
    detected_port: int


class OpenClawAdapter(Protocol):
    def read_status(self, engine) -> dict[str, object]: ...
    def read_health(self, engine) -> dict[str, object]: ...
    def run_doctor_repair(self, engine) -> bool: ...
    def detect_gateway_contract(self, engine, status_payload: dict[str, object] | None) -> GatewayContract: ...
```

The important point is not the exact class names. The important point is that the rest of the watchdog stops knowing whether service state came from `systemctl`, `launchctl`, `ss`, `lsof`, or a future OpenClaw CLI output change.

## Fast-follow strategy for an aggressive OpenClaw upstream

Do **not** center maintenance around version compatibility tables. Use these rules instead:

1. **Capability detection over version branching**
   Detect what the local OpenClaw binary and host can do now. Examples: whether `doctor --repair --non-interactive --yes` is accepted, whether status payload contains `gateway.url`, whether listener discovery requires `ss` or `lsof`.

2. **Fixture-backed contracts**
   Store representative upstream outputs under `tests/fixtures/openclaw_contracts/`. Unit tests should prove that the adapter can normalize old, current, and known-edge payload shapes into the watchdog’s canonical internal contract.

3. **Narrow integration seams**
   Only a small number of modules should ever parse upstream OpenClaw output directly. If upstream changes, those files are where change lands.

4. **Scout automation**
   Run a scheduled workflow against OpenClaw `main` or a pinned nightly snapshot. Capture CLI help, `doctor` usage shape, status payload samples, and any changed output fields. Fail softly with an issue or artifact, not with a surprise production regression.

5. **Replayable regression corpus**
   When upstream breaks something, add the exact broken sample to fixtures before changing parser code.

## Recommended execution order

1. `P0-1` Establish platform contracts and resolver
2. `P0-2` Move Linux `systemd` behavior behind the platform seam
3. `P0-3` Route detect and repair flows through adapters
4. `P1-1` Extract the OpenClaw upstream adapter and canonical contracts
5. `P1-2` Add upstream fixture corpus and scout automation
6. `P2-1` Add macOS `launchd` as an experimental adapter
7. `P2-2` Add install/docs support for macOS without overclaiming production readiness

This order keeps the architecture cut ahead of platform expansion. macOS should land only after Linux stops being the architecture.

---

## P0: Make Linux one adapter, not the design

### Task P0-1: Establish platform contracts and runtime resolution

**Files:**
- Create: `openclaw_watchdog/platforms/__init__.py`
- Create: `openclaw_watchdog/platforms/base.py`
- Create: `openclaw_watchdog/platforms/capabilities.py`
- Create: `openclaw_watchdog/platforms/resolver.py`
- Modify: `openclaw_watchdog/engine.py`
- Test: `tests/test_platform_resolver.py`

**Why this task exists**

Today the engine has no first-class concept of host capabilities or platform adapters. The first cut is to make the engine carry resolved host dependencies explicitly, so the rest of the code can stop reaching for Linux commands directly.

**Step 1: Write the failing tests**

Add a focused resolver test:

```python
class PlatformResolverTests(unittest.TestCase):
    def test_linux_systemd_user_resolves_linux_adapter(self):
        adapter = resolver.resolve_platform_adapter(
            host_family="linux",
            available_commands={"systemctl", "ss", "ps"},
            systemd_user_supported=True,
        )
        self.assertEqual(adapter.capabilities.supervisor, "systemd_user")
```

```python
    def test_missing_supervisor_falls_back_to_manual_capability(self):
        adapter = resolver.resolve_platform_adapter(
            host_family="darwin",
            available_commands={"lsof", "ps"},
            systemd_user_supported=False,
        )
        self.assertEqual(adapter.capabilities.supervisor, "manual")
```

**Step 2: Run the focused test to verify failure**

Run:

```bash
python3.13 -m unittest tests.test_platform_resolver -v
```

Expected: FAIL because the `platforms` package and resolver do not exist yet.

**Step 3: Write the minimal implementation**

Introduce the contracts and wire them onto the engine:

```python
@dataclass(frozen=True)
class ResolvedPlatform:
    capabilities: PlatformCapabilities
    supervisor: SupervisorAdapter
    listeners: ListenerAdapter
```

```python
class WatchdogEngine:
    def __init__(self, config: Config):
        ...
        self.platform = resolver.resolve_platform(self)
```

Keep the resolver simple. It only needs to decide between `linux_systemd`, `manual`, and a placeholder `macos_launchd` capability at first.

**Step 4: Run the focused test to verify it passes**

Run:

```bash
python3.13 -m unittest tests.test_platform_resolver -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add openclaw_watchdog/platforms openclaw_watchdog/engine.py tests/test_platform_resolver.py
git commit -m "refactor: introduce platform adapter contracts"
```

### Task P0-2: Move Linux `systemd` probing and restart logic behind the adapter

**Files:**
- Create: `openclaw_watchdog/platforms/linux_systemd.py`
- Modify: `openclaw_watchdog/service_runtime.py`
- Modify: `openclaw_watchdog/repair_action_runtime.py`
- Test: `tests/test_linux_systemd_adapter.py`
- Test: `tests/test_service_runtime.py`
- Test: `tests/test_repair_action_runtime.py`

**Why this task exists**

The current Linux coupling is concentrated in `service_runtime.py` and `repair_action_runtime.py`. The goal is to preserve behavior while relocating it into a Linux-specific owner that can later be paralleled by `macos_launchd.py`.

**Step 1: Write the failing tests**

Add adapter-focused coverage:

```python
class LinuxSystemdAdapterTests(unittest.TestCase):
    def test_restart_service_uses_systemctl_user(self):
        engine = make_engine()
        adapter = LinuxSystemdPlatform()
        adapter.restart_service(engine)
        self.assertEqual(
            engine.commands[:2],
            [
                ["systemctl", "--user", "reset-failed", "openclaw-gateway.service"],
                ["systemctl", "--user", "restart", "openclaw-gateway.service"],
            ],
        )
```

```python
    def test_listener_pids_reads_ss_output(self):
        ...
        self.assertEqual(adapter.listener_pids(engine), ["123", "456"])
```

**Step 2: Run the focused tests to verify failure**

Run:

```bash
python3.13 -m unittest tests.test_linux_systemd_adapter tests.test_service_runtime tests.test_repair_action_runtime -v
```

Expected: FAIL because the new adapter does not exist and legacy tests still assume direct helper ownership.

**Step 3: Write the minimal implementation**

Move the Linux-specific subprocess behavior into `linux_systemd.py`:

```python
class LinuxSystemdPlatform:
    capabilities = PlatformCapabilities(
        host_family="linux",
        supervisor="systemd_user",
        listener_tool="ss",
        supports_managed_restart=True,
        supports_listener_pid_tree=True,
    )
```

Keep `service_runtime.py` as a thin delegation layer for one transition step only:

```python
def service_active(engine) -> bool:
    return engine.platform.supervisor.service_active(engine)
```

```python
def restart_service(engine) -> bool:
    return engine.platform.supervisor.restart_service(engine)
```

**Step 4: Run the focused tests to verify they pass**

Run:

```bash
python3.13 -m unittest tests.test_linux_systemd_adapter tests.test_service_runtime tests.test_repair_action_runtime -v
```

Expected: PASS.

**Step 5: Run a broader regression slice**

Run:

```bash
python3.13 -m unittest tests.test_detect tests.test_service_runtime tests.test_repair_action_runtime -v
```

Expected: PASS, with no change in deterministic recovery order.

**Step 6: Commit**

```bash
git add openclaw_watchdog/platforms/linux_systemd.py openclaw_watchdog/service_runtime.py openclaw_watchdog/repair_action_runtime.py tests/test_linux_systemd_adapter.py tests/test_service_runtime.py tests/test_repair_action_runtime.py
git commit -m "refactor: move linux systemd behavior behind platform adapter"
```

### Task P0-3: Route service detection through the platform seam

**Files:**
- Modify: `openclaw_watchdog/detect_service_runtime.py`
- Modify: `openclaw_watchdog/detect.py`
- Modify: `openclaw_watchdog/health.py`
- Test: `tests/test_detect.py`
- Test: `tests/test_health.py`

**Why this task exists**

Even after the Linux adapter exists, detection still leaks `systemctl` assumptions. This task makes `detect` and health reporting read platform-normalized state instead of probing Linux commands inline.

**Step 1: Write the failing tests**

Add a detection contract test:

```python
def test_gateway_probe_reads_platform_normalized_service_details(self):
    engine.platform.supervisor.show_service_details.return_value = {
        "active_state": "active",
        "sub_state": "running",
    }
    payload = gateway_probe(engine, {"gateway": {"url": "http://127.0.0.1:8080"}})
    self.assertTrue(payload["service_active"])
```

**Step 2: Run the focused tests to verify failure**

Run:

```bash
python3.13 -m unittest tests.test_detect tests.test_health -v
```

Expected: FAIL because `gateway_probe()` still shells out to `systemctl`.

**Step 3: Write the minimal implementation**

Add one normalized adapter method such as:

```python
class SupervisorAdapter(Protocol):
    def describe_service(self, engine) -> dict[str, str]: ...
```

Then rewrite `gateway_probe()` to consume that normalized result instead of issuing `systemctl show` directly.

**Step 4: Run the focused tests to verify they pass**

Run:

```bash
python3.13 -m unittest tests.test_detect tests.test_health -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add openclaw_watchdog/detect_service_runtime.py openclaw_watchdog/detect.py openclaw_watchdog/health.py tests/test_detect.py tests/test_health.py
git commit -m "refactor: route service detection through platform contracts"
```

---

## P1: Isolate fast-moving OpenClaw behavior

### Task P1-1: Extract the OpenClaw upstream adapter and canonical contracts

**Files:**
- Create: `openclaw_watchdog/openclaw_runtime/__init__.py`
- Create: `openclaw_watchdog/openclaw_runtime/adapter.py`
- Create: `openclaw_watchdog/openclaw_runtime/capabilities.py`
- Create: `openclaw_watchdog/openclaw_runtime/contracts.py`
- Create: `openclaw_watchdog/openclaw_runtime/status_runtime.py`
- Create: `openclaw_watchdog/openclaw_runtime/config_runtime.py`
- Create: `openclaw_watchdog/openclaw_runtime/doctor_runtime.py`
- Modify: `openclaw_watchdog/detect_service_runtime.py`
- Modify: `openclaw_watchdog/doctor_runtime.py`
- Modify: `openclaw_watchdog/bootstrap_inventory.py`
- Modify: `openclaw_watchdog/bootstrap_inspectors.py`
- Test: `tests/test_openclaw_contracts.py`
- Test: `tests/test_detect.py`
- Test: `tests/test_doctor_runtime.py`

**Why this task exists**

OpenClaw upstream is the fast-changing dependency. The watchdog should not parse status payloads and CLI semantics directly from multiple places. This task creates a single normalization boundary.

**Step 1: Write the failing tests**

Create contract tests around normalized payload shape:

```python
def test_status_contract_normalizes_gateway_shape(self):
    raw = {"gateway": {"url": "http://127.0.0.1:3000", "reachable": "configured"}}
    contract = normalize_status_contract(raw)
    self.assertEqual(contract.gateway.url, "http://127.0.0.1:3000")
    self.assertTrue(contract.gateway.reachable)
```

```python
def test_doctor_capability_detects_supported_flags(self):
    help_text = "openclaw doctor --repair --non-interactive --yes"
    caps = detect_doctor_capabilities(help_text)
    self.assertTrue(caps.supports_non_interactive_yes)
```

**Step 2: Run the focused tests to verify failure**

Run:

```bash
python3.13 -m unittest tests.test_openclaw_contracts tests.test_detect tests.test_doctor_runtime -v
```

Expected: FAIL because the normalization helpers and capability detector do not exist yet.

**Step 3: Write the minimal implementation**

Create canonical contract dataclasses:

```python
@dataclass(frozen=True)
class GatewayStatus:
    url: str
    reachable: bool
    misconfigured: bool
```

```python
@dataclass(frozen=True)
class DoctorCapabilities:
    supports_repair: bool
    supports_non_interactive_yes: bool
```

The legacy top-level `doctor_runtime.py` can temporarily delegate into `openclaw_runtime.doctor_runtime` while call sites are migrated.

**Step 4: Run the focused tests to verify they pass**

Run:

```bash
python3.13 -m unittest tests.test_openclaw_contracts tests.test_detect tests.test_doctor_runtime -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add openclaw_watchdog/openclaw_runtime openclaw_watchdog/detect_service_runtime.py openclaw_watchdog/doctor_runtime.py openclaw_watchdog/bootstrap_inventory.py openclaw_watchdog/bootstrap_inspectors.py tests/test_openclaw_contracts.py tests/test_detect.py tests/test_doctor_runtime.py
git commit -m "refactor: isolate openclaw upstream contracts"
```

### Task P1-2: Add upstream fixture corpus and scout automation

**Files:**
- Create: `tests/fixtures/openclaw_contracts/status/current.json`
- Create: `tests/fixtures/openclaw_contracts/status/legacy.json`
- Create: `tests/fixtures/openclaw_contracts/status/edge-missing-gateway.json`
- Create: `tests/fixtures/openclaw_contracts/doctor/help-current.txt`
- Create: `tests/fixtures/openclaw_contracts/doctor/help-legacy.txt`
- Create: `scripts/scout-openclaw-upstream.sh`
- Create: `.github/workflows/openclaw-upstream-scout.yml`
- Create: `docs/upstream-tracking.md`
- Modify: `tests/test_openclaw_contracts.py`

**Why this task exists**

Without a replayable fixture corpus, every upstream break gets rediscovered the hard way. Without a scout job, the repo only learns about upstream changes after a human notices a regression.

**Step 1: Write the failing tests**

Add fixture-driven tests:

```python
def test_all_status_fixtures_normalize(self):
    for name in ["current", "legacy", "edge-missing-gateway"]:
        raw = json.loads(Path(f"tests/fixtures/openclaw_contracts/status/{name}.json").read_text())
        contract = normalize_status_contract(raw)
        self.assertIsNotNone(contract.gateway)
```

**Step 2: Run the focused tests to verify failure**

Run:

```bash
python3.13 -m unittest tests.test_openclaw_contracts -v
```

Expected: FAIL because the new fixtures and coverage do not exist yet.

**Step 3: Write the minimal implementation**

Create a scout script that captures:

- `openclaw --help`
- `openclaw doctor --help`
- one read-only status sample if available
- detected flag and field inventory written to an artifact directory

The workflow should run on a schedule and on demand, upload artifacts, and open or update an issue when the normalized contract changes.

**Step 4: Run the focused tests to verify they pass**

Run:

```bash
python3.13 -m unittest tests.test_openclaw_contracts -v
```

Expected: PASS.

**Step 5: Smoke-check the scout script locally**

Run:

```bash
bash scripts/scout-openclaw-upstream.sh
```

Expected: the script exits cleanly, even if some read-only probes are unavailable, and writes a deterministic artifact directory.

**Step 6: Commit**

```bash
git add tests/fixtures/openclaw_contracts scripts/scout-openclaw-upstream.sh .github/workflows/openclaw-upstream-scout.yml docs/upstream-tracking.md tests/test_openclaw_contracts.py
git commit -m "test: add openclaw upstream fixture corpus and scout automation"
```

---

## P2: Add macOS after the seams exist

### Task P2-1: Introduce an experimental `launchd` platform adapter

**Files:**
- Create: `openclaw_watchdog/platforms/macos_launchd.py`
- Modify: `openclaw_watchdog/platforms/resolver.py`
- Modify: `openclaw_watchdog/service_runtime.py`
- Modify: `openclaw_watchdog/repair_action_runtime.py`
- Test: `tests/test_macos_launchd_adapter.py`
- Test: `tests/test_platform_resolver.py`

**Why this task exists**

macOS support should be added only after the runtime already thinks in platform contracts. At that point, `launchd` becomes just another adapter, not a second architecture.

**Step 1: Write the failing tests**

Add resolver and adapter coverage:

```python
class MacosLaunchdAdapterTests(unittest.TestCase):
    def test_resolver_selects_launchd_on_darwin(self):
        adapter = resolver.resolve_platform_adapter(
            host_family="darwin",
            available_commands={"launchctl", "lsof", "ps"},
            systemd_user_supported=False,
        )
        self.assertEqual(adapter.capabilities.supervisor, "launchd")
```

```python
    def test_listener_pids_reads_lsof_output(self):
        ...
        self.assertEqual(adapter.listener_pids(engine), ["321"])
```

**Step 2: Run the focused tests to verify failure**

Run:

```bash
python3.13 -m unittest tests.test_macos_launchd_adapter tests.test_platform_resolver -v
```

Expected: FAIL because there is no `launchd` adapter yet.

**Step 3: Write the minimal implementation**

Implement the smallest useful `launchd` adapter:

- `service_active()` via `launchctl print gui/$UID/<label>` or normalized `launchctl list`
- `service_main_pid()` from the same output
- `listener_pids()` via `lsof -nP -iTCP:<port> -sTCP:LISTEN`
- `restart_service()` via `launchctl kickstart -k`

Do not promise full operator install automation yet. The adapter is experimental until live acceptance exists.

**Step 4: Run the focused tests to verify they pass**

Run:

```bash
python3.13 -m unittest tests.test_macos_launchd_adapter tests.test_platform_resolver tests.test_service_runtime tests.test_repair_action_runtime -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add openclaw_watchdog/platforms/macos_launchd.py openclaw_watchdog/platforms/resolver.py openclaw_watchdog/service_runtime.py openclaw_watchdog/repair_action_runtime.py tests/test_macos_launchd_adapter.py tests/test_platform_resolver.py
git commit -m "feat: add experimental macos launchd adapter"
```

### Task P2-2: Add macOS install path and support-policy wording

**Files:**
- Create: `launchd/com.eudonline.openclaw-watchdog.plist`
- Create: `scripts/install-openclaw-watchdog-launchd.sh`
- Modify: `README.md`
- Modify: `docs/first-deployment.md`
- Modify: `docs/supported-environments.md`
- Modify: `docs/internal-architecture.md`
- Test: `tests/test_docs_surface.py`

**Why this task exists**

Once the runtime supports a `launchd` adapter, the docs must explain the new shape honestly: Linux remains the first verified path until real live acceptance exists, while macOS is architecture-supported and explicitly experimental.

**Step 1: Write the failing tests**

Add a docs-surface assertion:

```python
def test_supported_environments_mentions_experimental_macos_adapter(self):
    text = Path("docs/supported-environments.md").read_text(encoding="utf-8")
    self.assertIn("macOS", text)
    self.assertIn("experimental", text)
```

**Step 2: Run the focused test to verify failure**

Run:

```bash
python3.13 -m unittest tests.test_docs_surface -v
```

Expected: FAIL because the current public docs still describe Linux + `systemd --user` as the only host path.

**Step 3: Write the minimal implementation**

Update docs to say:

- architecture is now platform-adapter based
- Linux + `systemd --user` is the first live-validated deployment path
- macOS + `launchd` is experimental until live acceptance and release evidence exist

**Step 4: Run the focused test to verify it passes**

Run:

```bash
python3.13 -m unittest tests.test_docs_surface -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add launchd/com.eudonline.openclaw-watchdog.plist scripts/install-openclaw-watchdog-launchd.sh README.md docs/first-deployment.md docs/supported-environments.md docs/internal-architecture.md tests/test_docs_surface.py
git commit -m "docs: document experimental macos launchd path"
```

---

## Guardrails and non-goals

### Guardrails

- Do not spread platform conditionals through `flows/` or operator-presenter code.
- Do not build a version matrix for OpenClaw if capability probes and fixtures can answer the same question.
- Do not let more than a small handful of files parse upstream CLI output directly.
- Keep deterministic recovery order unchanged while moving seams.
- Keep the rehearsal harness valuable by shifting it toward normalized contracts, not Linux-only assumptions.

### Non-goals

- Do not generalize the watchdog into a multi-product orchestration framework.
- Do not promise production-grade macOS support before live acceptance exists.
- Do not spend time on backward-compatibility shims for internal module paths unless a test proves they are still required.

## Verification checklist for plan execution

At the end of the full plan, the repo should be able to prove these statements:

1. Linux behavior still passes existing detect, repair, and rehearsal coverage.
2. The engine resolves a first-class platform adapter instead of assuming Linux commands inline.
3. OpenClaw status and doctor parsing run through a canonical contract layer backed by fixtures.
4. A scheduled scout job can detect upstream output drift before operators do.
5. macOS support lands as a clean `launchd` adapter, not as scattered `darwin` branches.

## Expected outcome

If this plan is followed, the project becomes easier to extend in exactly the two dimensions that matter most:

- **new host platforms**, especially macOS
- **new OpenClaw upstream behaviors**, even when they change quickly

That is the right trade because the project has not been deployed yet. This is the cheapest moment to correct the architecture.
