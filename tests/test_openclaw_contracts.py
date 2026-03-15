from __future__ import annotations

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


if __name__ == '__main__':
    unittest.main()
