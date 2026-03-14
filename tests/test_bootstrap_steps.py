from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from openclaw_watchdog.bootstrap import BootstrapOutcome, Bootstrapper
from openclaw_watchdog.bootstrap_steps import PipelineResult, run_bootstrap_pipeline
from openclaw_watchdog.models import BootstrapSummary


class _Result:
    def __init__(self, returncode: int):
        self.returncode = returncode


class FakeBootstrapper:
    def __init__(self) -> None:
        self.allow_install = False
        self.config = SimpleNamespace(
            openclaw_config=Path('state/openclaw.json'),
            watchdog_codex_bin='codex',
            watchdog_opencode_bin='opencode',
            watchdog_litellm_enabled=False,
            watchdog_litellm_model='',
        )
        self._opencode = {
            'available': True,
            'detected_binary': 'opencode',
            'watchdog_bin_available': True,
            'config_ready': True,
        }
        self._codex = {'available': True, 'configured_available': True, 'detected_binary': 'codex'}
        self._claude_code = {'available': False, 'detected_binary': ''}
        self._gemini_cli = {'available': False, 'detected_binary': ''}
        self._litellm = {'available': False, 'enabled': False, 'configured': False, 'model': ''}
        self._openclaw = {'available': True, 'binary': '/usr/local/bin/openclaw', 'detect_returncode': 0}
        self._qq_plugin = {'status': 'ready', 'installed': True, 'detect_returncode': 0}
        self._config_payload = {
            'status': 'ready',
            'changed': False,
            'path': 'state/openclaw.json',
            'channels': {'qqbot': {'enabled': True}, 'feishu': {'enabled': False}},
            'placeholders_remaining': [],
        }
        self._feishu_runtime = {'checked': True, 'found': True}

    def detect_opencode(self):
        return dict(self._opencode)

    def detect_codex(self):
        return dict(self._codex)

    def detect_claude_code(self):
        return dict(self._claude_code)

    def detect_gemini_cli(self):
        return dict(self._gemini_cli)

    def detect_litellm(self):
        return dict(self._litellm)

    def detect_openclaw(self):
        return dict(self._openclaw)

    def inspect_qq_plugin(self):
        return dict(self._qq_plugin)

    def inspect_default_channel_config(self):
        return dict(self._config_payload)

    def detect_feishu_runtime_markers(self):
        return dict(self._feishu_runtime)

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
    def test_detect_only_bootstrap_reports_executor_inventory_without_installing(self) -> None:
        bootstrapper = FakeBootstrapper()
        bootstrapper._claude_code = {'available': False, 'detected_binary': ''}
        bootstrapper._gemini_cli = {'available': True, 'detected_binary': 'gemini'}
        bootstrapper._opencode = {
            'available': False,
            'detected_binary': '',
            'watchdog_bin_available': False,
            'config_ready': False,
        }

        result = run_bootstrap_pipeline(
            bootstrapper,
            BootstrapSummary.initial(config_path='state/openclaw.json'),
        )

        self.assertEqual(result.state, 'attention')
        self.assertEqual(result.exit_code, 0)
        self.assertEqual(result.bootstrap_summary.executors['codex']['available'], True)
        self.assertEqual(result.bootstrap_summary.executors['claude-code']['available'], False)
        self.assertEqual(result.bootstrap_summary.executors['gemini-cli']['available'], True)
        self.assertEqual(result.bootstrap_summary.executors['opencode']['available'], False)
        self.assertEqual(result.bootstrap_summary.executors['litellm']['available'], False)

    def test_missing_openclaw_adds_manual_next_step_without_confirmation_stop(self) -> None:
        bootstrapper = FakeBootstrapper()
        bootstrapper._openclaw = {'available': False, 'binary': '', 'detect_returncode': 1}

        result = run_bootstrap_pipeline(
            bootstrapper,
            BootstrapSummary.initial(config_path='state/openclaw.json'),
        )

        self.assertEqual(result.state, 'attention')
        self.assertFalse(result.bootstrap_summary.openclaw['available'])
        self.assertIn('Install or expose OpenClaw on PATH before enabling live rescue flows.', result.bootstrap_summary.next_steps)

    def test_placeholder_credentials_keep_warning_and_next_step(self) -> None:
        bootstrapper = FakeBootstrapper()
        bootstrapper._config_payload = {
            'status': 'ready',
            'changed': False,
            'path': 'state/openclaw.json',
            'channels': {'qqbot': {'enabled': True}, 'feishu': {'enabled': False}},
            'placeholders_remaining': ['qqbot.appid', 'feishu.appSecret'],
        }
        bootstrapper._feishu_runtime = {'checked': True, 'found': False}

        result = run_bootstrap_pipeline(
            bootstrapper,
            BootstrapSummary.initial(config_path='state/openclaw.json'),
        )

        self.assertIn('fill placeholder credentials before enabling live traffic', result.bootstrap_summary.warnings)
        self.assertIn(
            'Fill the placeholder credentials, review enabled flags for qqbot/feishu, then restart the gateway manually.',
            result.bootstrap_summary.next_steps,
        )
        self.assertIn('Feishu runtime markers were not observed in logs yet', result.bootstrap_summary.warnings)

    def test_bootstrapper_run_passes_bootstrap_summary_into_finish(self) -> None:
        config = SimpleNamespace(
            openclaw_config=Path('state/openclaw.json'),
            watchdog_codex_bin='codex',
            watchdog_opencode_bin='opencode',
            watchdog_litellm_enabled=False,
            watchdog_litellm_model='',
        )

        class RecordingBootstrapper(Bootstrapper):
            def __init__(self) -> None:
                super().__init__(config)
                self.received_summary = None

            def finish(self, bootstrap_summary, *, state: str, summary: str, exit_code: int) -> BootstrapOutcome:
                self.received_summary = bootstrap_summary
                return BootstrapOutcome(exit_code=exit_code, state=state, summary=summary, payload={})

        bootstrap_summary = BootstrapSummary.initial(config_path='state/openclaw.json')
        bootstrap_summary.executors = {'codex': {'available': True}}
        bootstrapper = RecordingBootstrapper()

        with patch(
            'openclaw_watchdog.bootstrap.bootstrap_step_ops.run_bootstrap_pipeline',
            return_value=PipelineResult(
                bootstrap_summary=bootstrap_summary,
                state='attention',
                message='ok',
                exit_code=0,
            ),
        ):
            bootstrapper.run()

        self.assertIsInstance(bootstrapper.received_summary, BootstrapSummary)

    def test_bootstrapper_finish_accepts_bootstrap_summary_without_round_trip(self) -> None:
        config = SimpleNamespace(
            openclaw_config=Path('state/openclaw.json'),
            watchdog_codex_bin='codex',
            watchdog_opencode_bin='opencode',
            watchdog_litellm_enabled=False,
            watchdog_litellm_model='',
        )
        bootstrapper = Bootstrapper(config)
        bootstrap_summary = BootstrapSummary.initial(config_path='state/openclaw.json')
        bootstrap_summary.executors = {
            'codex': {'available': True, 'detected_binary': 'codex'},
            'claude-code': {'available': False, 'detected_binary': ''},
        }
        bootstrap_summary.config = {
            'path': 'state/openclaw.json',
            'changed': False,
            'backup_path': '',
        }

        outcome = bootstrapper.finish(bootstrap_summary, state='attention', summary='ok', exit_code=0)

        self.assertNotIn('files_changed', outcome.payload)
        self.assertNotIn('backup_files', outcome.payload)
        self.assertNotIn('dry_run', outcome.payload)
        self.assertEqual(outcome.payload['state'], 'attention')
        self.assertEqual(outcome.payload['summary'], 'ok')
        self.assertEqual(outcome.payload['exit_code'], 0)
        self.assertEqual(outcome.payload['executors']['codex']['available'], True)

    def test_detect_opencode_populates_watchdog_binary_status(self) -> None:
        config = SimpleNamespace(
            openclaw_config=Path('state/openclaw.json'),
            watchdog_codex_bin='codex',
            watchdog_opencode_bin='opencode-watchdog',
            watchdog_litellm_enabled=False,
            watchdog_litellm_model='',
        )
        bootstrapper = Bootstrapper(config)

        with patch.object(bootstrapper, 'detect_binary', side_effect=[(True, '/usr/local/bin/opencode', _Result(0)), (True, '/usr/local/bin/opencode-watchdog', _Result(0))]):
            with patch.object(bootstrapper, 'inspect_opencode_config', return_value={'path': 'state/opencode.json', 'ready': True}):
                payload = bootstrapper.detect_opencode()

        self.assertTrue(payload['available'])
        self.assertTrue(payload['watchdog_bin_available'])
        self.assertEqual(payload['watchdog_binary'], '/usr/local/bin/opencode-watchdog')
        self.assertTrue(payload['config_ready'])



if __name__ == '__main__':
    unittest.main()
