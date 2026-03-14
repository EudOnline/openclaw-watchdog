from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch


class RollbackRuntimeTests(unittest.TestCase):
    def test_last_good_candidates_fall_back_to_legacy_last_good_file_without_manifest(self) -> None:
        from openclaw_watchdog import generation_runtime

        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            last_good_config = root / 'openclaw.last-good.json'
            last_good_config.write_text(json.dumps({'channels': {'qqbot': {'enabled': True}}}), encoding='utf-8')
            engine = SimpleNamespace(
                config=SimpleNamespace(
                    watchdog_last_good_manifest_file=root / 'last-good-manifest.json',
                    watchdog_last_good_config=last_good_config,
                )
            )

            candidates = generation_runtime.last_good_candidates(engine)

        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0]['generation_id'], 'legacy-last-good')
        self.assertEqual(candidates[0]['path'], str(last_good_config))

    def test_restore_last_good_uses_generation_runtime_candidates_directly(self) -> None:
        from openclaw_watchdog import rollback_runtime

        engine = SimpleNamespace()
        generation = SimpleNamespace(last_good_candidates=Mock(return_value=[]))

        with patch.object(rollback_runtime, 'generation_runtime', generation, create=True):
            restored = rollback_runtime.restore_last_good(engine, reason='unit-test')

        self.assertFalse(restored)
        generation.last_good_candidates.assert_called_once_with(engine)

    def test_walk_json_diff_tracks_nested_object_changes(self) -> None:
        from openclaw_watchdog import rollback_runtime

        out: list[str] = []

        rollback_runtime.walk_json_diff(
            {'channels': {'qqbot': {'enabled': True, 'name': 'a'}}},
            {'channels': {'qqbot': {'enabled': False, 'name': 'a'}, 'feishu': {'enabled': True}}},
            '',
            out,
            limit=10,
        )

        self.assertIn('channels.feishu: added', out)
        self.assertIn('channels.qqbot.enabled: true -> false', ' | '.join(out).lower())

    def test_capture_rollback_summary_persists_json_summary_and_ctx_excerpt(self) -> None:
        from openclaw_watchdog import rollback_runtime

        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            current = root / 'current.json'
            baseline = root / 'baseline.json'
            summary_file = root / 'rollback-summary.txt'
            current.write_text(json.dumps({'channels': {'qqbot': {'enabled': True}}}), encoding='utf-8')
            baseline.write_text(json.dumps({'channels': {'qqbot': {'enabled': False}}}), encoding='utf-8')
            logs: list[tuple[str, str]] = []
            engine = SimpleNamespace(
                config=SimpleNamespace(watchdog_last_rollback_summary_file=summary_file),
                ctx=SimpleNamespace(rollback_summary=''),
                log=lambda level, message: logs.append((level, message)),
            )

            rollback_runtime.capture_rollback_summary(engine, current, baseline)

            written = summary_file.read_text(encoding='utf-8')

        self.assertIn('current -> last-good JSON diff summary', written)
        self.assertIn('channels.qqbot.enabled', written)
        self.assertIn('channels.qqbot.enabled', engine.ctx.rollback_summary)
        self.assertEqual(logs, [('WARN', f'rollback summary saved: {summary_file}')])


if __name__ == '__main__':
    unittest.main()
