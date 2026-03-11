from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
import unittest

from watchdog_v2.bootstrap_steps import run_bootstrap_pipeline
from watchdog_v2.models import BootstrapSummary


class _Result:
    def __init__(self, returncode: int):
        self.returncode = returncode


class FakeBootstrapper:
    def __init__(self, *, allow_install: bool = False, dry_run: bool = False) -> None:
        self.allow_install = allow_install
        self.dry_run = dry_run
        self.config = SimpleNamespace(
            openclaw_config=Path('state/openclaw.json'),
            openclaw_install_command='curl -fsSL install-openclaw.sh | bash',
            watchdog_opencode_fallback_bin='opencode',
        )
        self._opencode = {'status': 'ready', 'changed': False, 'watchdog_bin_available': True, 'config': {'path': 'state/opencode.json', 'changed': False, 'backup_path': ''}}
        self._codex = {'available': True, 'configured_available': True, 'detected_binary': 'codex'}
        self._detect_openclaw = (True, '/usr/local/bin/openclaw', _Result(0))
        self._ensure_openclaw = {'installed': True, 'changed': False}
        self._qq_plugin = {'status': 'ready', 'installed': True, 'changed': False}
        self._config_payload = {'status': 'ready', 'changed': False, 'path': 'state/openclaw.json', 'backup_path': '', 'channels': {'qqbot': {'enabled': True}, 'feishu': {'enabled': False}}, 'placeholders_remaining': []}
        self._feishu_runtime = {'checked': True, 'found': True}

    def ensure_opencode(self):
        return dict(self._opencode)

    def detect_codex(self):
        return dict(self._codex)

    def detect_openclaw(self):
        return self._detect_openclaw

    def ensure_openclaw(self, installed: bool):
        return dict(self._ensure_openclaw)

    def ensure_qq_plugin(self):
        return dict(self._qq_plugin)

    def ensure_default_channel_config(self):
        return dict(self._config_payload)

    def detect_feishu_runtime_markers(self):
        return dict(self._feishu_runtime)

    def openclaw_confirmation_summary(self, opencode_payload):
        return 'OpenClaw missing; rerun with --install-openclaw.'

    def unique_nonempty(self, values):
        seen = set()
        ordered = []
        for value in values:
            if not value or value in seen:
                continue
            seen.add(value)
            ordered.append(value)
        return ordered


class BootstrapStepsTest(unittest.TestCase):
    def test_missing_openclaw_without_confirmation_stops_with_exit_10(self) -> None:
        bootstrapper = FakeBootstrapper(allow_install=False)
        bootstrapper._codex = {'available': False, 'configured_available': False, 'detected_binary': ''}
        bootstrapper._detect_openclaw = (False, '', _Result(1))

        result = run_bootstrap_pipeline(
            bootstrapper,
            BootstrapSummary.initial(config_path='state/openclaw.json', dry_run=False),
        )

        self.assertEqual(result.state, 'confirmation-required')
        self.assertEqual(result.exit_code, 10)
        self.assertTrue(result.bootstrap_summary.openclaw['confirmation_required'])
        self.assertIn('Rerun bootstrap with --install-openclaw once you want the install command to execute.', result.bootstrap_summary.next_steps)

    def test_opencode_config_change_is_preserved_in_summary(self) -> None:
        bootstrapper = FakeBootstrapper()
        bootstrapper._opencode = {
            'status': 'ready',
            'changed': True,
            'watchdog_bin_available': True,
            'config': {
                'path': 'state/opencode.json',
                'changed': True,
                'backup_path': 'state/opencode.backup.json',
            },
        }
        bootstrapper._config_payload['changed'] = True

        result = run_bootstrap_pipeline(
            bootstrapper,
            BootstrapSummary.initial(config_path='state/openclaw.json', dry_run=False),
        )

        self.assertEqual(result.state, 'bootstrapped')
        self.assertTrue(result.bootstrap_summary.opencode['changed'])
        self.assertTrue(result.bootstrap_summary.opencode['config']['changed'])
        self.assertEqual(result.bootstrap_summary.opencode['config']['path'], 'state/opencode.json')

    def test_plugin_install_failure_bubbles_up_as_failed_state(self) -> None:
        bootstrapper = FakeBootstrapper()
        bootstrapper._qq_plugin = {'status': 'failed', 'installed': False, 'changed': False}

        result = run_bootstrap_pipeline(
            bootstrapper,
            BootstrapSummary.initial(config_path='state/openclaw.json', dry_run=False),
        )

        self.assertEqual(result.state, 'failed')
        self.assertEqual(result.message, 'QQ plugin install failed')

    def test_placeholder_credentials_keep_warning_and_next_step(self) -> None:
        bootstrapper = FakeBootstrapper()
        bootstrapper._config_payload = {
            'status': 'ready',
            'changed': True,
            'path': 'state/openclaw.json',
            'backup_path': '',
            'channels': {'qqbot': {'enabled': True}, 'feishu': {'enabled': False}},
            'placeholders_remaining': ['qqbot.appid', 'feishu.appSecret'],
        }
        bootstrapper._feishu_runtime = {'checked': True, 'found': False}

        result = run_bootstrap_pipeline(
            bootstrapper,
            BootstrapSummary.initial(config_path='state/openclaw.json', dry_run=False),
        )

        self.assertIn('fill placeholder credentials before enabling live traffic', result.bootstrap_summary.warnings)
        self.assertIn(
            'Fill the placeholder credentials, review enabled flags for qqbot/feishu, then restart the gateway manually.',
            result.bootstrap_summary.next_steps,
        )
        self.assertIn('Feishu runtime markers were not observed in logs yet', result.bootstrap_summary.warnings)


if __name__ == '__main__':
    unittest.main()
