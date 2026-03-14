from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch


class LastGoodRuntimeTests(unittest.TestCase):
    def test_apply_drift_context_updates_engine_ctx_fields(self) -> None:
        from openclaw_watchdog import last_good_runtime

        engine = SimpleNamespace(
            ctx=SimpleNamespace(
                config_drift_detected=False,
                drift_scope=[],
                drift_since_last_good='',
                drift_summary='',
            )
        )

        payload = last_good_runtime.apply_drift_context(
            engine,
            {
                'detected': True,
                'scope': ['openclaw_config', 'env_file'],
                'since_last_good': 'generation=gen-2 validated_at=2026-03-12T08:00:00+08:00',
                'summary': 'protected paths changed since last-good: openclaw_config, env_file',
            },
        )

        self.assertTrue(payload['detected'])
        self.assertTrue(engine.ctx.config_drift_detected)
        self.assertEqual(engine.ctx.drift_scope, ['openclaw_config', 'env_file'])
        self.assertIn('generation=gen-2', engine.ctx.drift_since_last_good)
        self.assertIn('protected paths changed', engine.ctx.drift_summary)

    def test_guard_status_reads_latest_event_from_manifest(self) -> None:
        from openclaw_watchdog import guard_runtime

        with TemporaryDirectory() as temp_dir:
            manifest_file = Path(temp_dir) / 'guard.json'
            manifest_file.write_text(
                json.dumps(
                    {
                        'events': [
                            {
                                'operation': 'restore-last-good',
                                'phase': 'after',
                                'time': '2026-03-12T20:30:00+08:00',
                                'summary': 'after | restore-last-good | changed=openclaw_config',
                            }
                        ],
                        'latest_snapshot': [],
                    },
                    ensure_ascii=False,
                    indent=2,
                    sort_keys=True,
                ) + '\n',
                encoding='utf-8',
            )

            payload = guard_runtime.guard_status(
                SimpleNamespace(watchdog_guard_manifest_file=manifest_file)
            )

        self.assertEqual(payload['guard_last_operation'], 'restore-last-good')
        self.assertEqual(payload['guard_last_phase'], 'after')
        self.assertEqual(payload['guard_last_time'], '2026-03-12T20:30:00+08:00')
        self.assertIn('changed=openclaw_config', payload['guard_last_summary'])

    def test_protected_paths_snapshot_deduplicates_canonical_paths(self) -> None:
        from openclaw_watchdog import guard_runtime

        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            openclaw_config = root / 'openclaw.json'
            env_file = root / '.env'
            survival_file = root / 'survival.json'
            extensions_dir = openclaw_config.parent / 'extensions'
            openclaw_config.write_text('{"channels": {}}', encoding='utf-8')
            env_file.write_text('OPENCLAW_ENV=test\n', encoding='utf-8')
            survival_file.write_text('{}', encoding='utf-8')
            extensions_dir.mkdir(parents=True, exist_ok=True)

            snapshot = guard_runtime.protected_paths_snapshot(
                SimpleNamespace(
                    openclaw_config=openclaw_config,
                    env_file=env_file,
                    watchdog_survival_config_file=survival_file,
                    watchdog_protected_paths=(
                        str(openclaw_config),
                        str(env_file),
                        str(extensions_dir),
                    ),
                )
            )

        self.assertEqual(
            [item['label'] for item in snapshot],
            ['openclaw_config', 'env_file', 'openclaw_extensions', 'watchdog_survival_config'],
        )

    def test_last_good_facade_delegates_to_guard_and_generation_runtimes(self) -> None:
        from openclaw_watchdog import last_good_runtime

        config = object()
        engine = object()
        guard = SimpleNamespace(
            protected_paths_snapshot=Mock(return_value=[{'label': 'openclaw_config'}]),
            guard_status=Mock(return_value={'guard_last_operation': 'validate'}),
        )
        generation = SimpleNamespace(
            last_good_candidates=Mock(return_value=[{'generation_id': 'gen-1'}]),
            last_good_status=Mock(return_value={'last_good_generation_id': 'gen-1'}),
        )

        with patch.object(last_good_runtime, 'guard_runtime', guard, create=True):
            snapshot = last_good_runtime.protected_paths_snapshot(config)
            guard_status = last_good_runtime.guard_status(config)
        with patch.object(last_good_runtime, 'generation_runtime', generation, create=True):
            candidates = last_good_runtime.last_good_candidates(engine)
            status = last_good_runtime.last_good_status(engine)

        self.assertEqual(snapshot, [{'label': 'openclaw_config'}])
        self.assertEqual(guard_status, {'guard_last_operation': 'validate'})
        self.assertEqual(candidates, [{'generation_id': 'gen-1'}])
        self.assertEqual(status, {'last_good_generation_id': 'gen-1'})
        guard.protected_paths_snapshot.assert_called_once_with(config)
        guard.guard_status.assert_called_once_with(config)
        generation.last_good_candidates.assert_called_once_with(engine)
        generation.last_good_status.assert_called_once_with(engine)


if __name__ == '__main__':
    unittest.main()
