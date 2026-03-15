from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest


class OpenClawContractsTests(unittest.TestCase):
    def test_status_contract_normalizes_gateway_shape(self) -> None:
        from openclaw_watchdog.openclaw_runtime import status_runtime

        contract = status_runtime.normalize_status_contract(
            {
                'gateway': {
                    'url': 'http://127.0.0.1:3000',
                    'reachable': 'configured',
                    'misconfigured': 'not-configured',
                }
            },
            configured_port=5700,
        )

        self.assertEqual(contract.gateway.url, 'http://127.0.0.1:3000')
        self.assertTrue(contract.gateway.reachable)
        self.assertFalse(contract.gateway.misconfigured)
        self.assertEqual(contract.gateway.configured_port, 5700)
        self.assertEqual(contract.gateway.detected_port, 3000)

    def test_detect_doctor_capabilities_supports_non_interactive_yes(self) -> None:
        from openclaw_watchdog.openclaw_runtime import doctor_runtime

        caps = doctor_runtime.detect_doctor_capabilities(
            '\n'.join(
                [
                    'Usage: openclaw doctor [options]',
                    '  --repair',
                    '  --non-interactive',
                    '  --yes',
                ]
            )
        )

        self.assertTrue(caps.supports_repair)
        self.assertTrue(caps.supports_non_interactive)
        self.assertTrue(caps.supports_yes)
        self.assertTrue(caps.supports_non_interactive_yes)

    def test_load_json_object_accepts_jsonc_when_enabled(self) -> None:
        from openclaw_watchdog.openclaw_runtime import config_runtime

        with TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / 'opencode.jsonc'
            path.write_text(
                '\n'.join(
                    [
                        '{',
                        '  // comment',
                        '  "model": "opencode/minimax-m2.5-free",',
                        '}',
                    ]
                ),
                encoding='utf-8',
            )

            payload = config_runtime.load_json_object(path, label='existing OpenCode config', allow_jsonc=True)

        self.assertEqual(payload['model'], 'opencode/minimax-m2.5-free')

    def test_bootstrap_detect_openclaw_includes_doctor_capabilities(self) -> None:
        from openclaw_watchdog import bootstrap_inventory

        bootstrapper = SimpleNamespace(
            _detect_openclaw_binary=lambda: (True, '/usr/local/bin/openclaw', SimpleNamespace(returncode=0)),
            run_shell=lambda command, timeout=None: SimpleNamespace(
                returncode=0,
                output='Usage: openclaw doctor\n  --repair\n  --non-interactive\n  --yes\n',
            ),
        )

        payload = bootstrap_inventory.detect_openclaw(bootstrapper)

        self.assertTrue(payload['available'])
        self.assertEqual(payload['binary'], '/usr/local/bin/openclaw')
        self.assertEqual(payload['doctor_help_returncode'], 0)
        self.assertTrue(payload['doctor_capabilities']['supports_non_interactive_yes'])

    def test_all_status_fixtures_normalize(self) -> None:
        from openclaw_watchdog.openclaw_runtime import status_runtime

        fixture_dir = Path('tests/fixtures/openclaw_contracts/status')
        for name in ['current', 'legacy', 'edge-missing-gateway']:
            with self.subTest(name=name):
                raw = json.loads((fixture_dir / f'{name}.json').read_text(encoding='utf-8'))
                contract = status_runtime.normalize_status_contract(raw, configured_port=5700)
                self.assertEqual(contract.gateway.configured_port, 5700)

    def test_doctor_help_fixtures_capture_capability_differences(self) -> None:
        from openclaw_watchdog.openclaw_runtime import doctor_runtime

        fixture_dir = Path('tests/fixtures/openclaw_contracts/doctor')
        current = doctor_runtime.detect_doctor_capabilities((fixture_dir / 'help-current.txt').read_text(encoding='utf-8'))
        legacy = doctor_runtime.detect_doctor_capabilities((fixture_dir / 'help-legacy.txt').read_text(encoding='utf-8'))

        self.assertTrue(current.supports_non_interactive_yes)
        self.assertFalse(legacy.supports_non_interactive_yes)

    def test_upstream_scout_workflow_references_script_and_artifacts(self) -> None:
        workflow_text = Path('.github/workflows/openclaw-upstream-scout.yml').read_text(encoding='utf-8')

        self.assertIn('workflow_dispatch:', workflow_text)
        self.assertIn('schedule:', workflow_text)
        self.assertIn('bash scripts/scout-openclaw-upstream.sh', workflow_text)
        self.assertIn('actions/upload-artifact', workflow_text)

    def test_upstream_tracking_doc_references_fixtures_and_script(self) -> None:
        doc_text = Path('docs/upstream-tracking.md').read_text(encoding='utf-8')

        self.assertIn('tests/fixtures/openclaw_contracts', doc_text)
        self.assertIn('scripts/scout-openclaw-upstream.sh', doc_text)
        self.assertIn('openclaw-upstream-scout.yml', doc_text)


if __name__ == '__main__':
    unittest.main()
