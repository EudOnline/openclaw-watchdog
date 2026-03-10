import tempfile
import unittest
from pathlib import Path

from watchdog_v2.state_store import append_event_history, read_event_history, read_run_state, sibling_json_path, write_run_state


class StateStoreTest(unittest.TestCase):
    def test_read_and_write_run_state(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            run_state_file = Path(temp_dir) / 'run-state.json'

            state = read_run_state(run_state_file, stable_required_runs=3)
            self.assertEqual(state['current_mode'], 'normal')
            self.assertEqual(state['survival_mode_stable_required_runs'], 3)

            updated = write_run_state(run_state_file, {'health_level': 'healthy', 'conversation_ready': True}, stable_required_runs=3)
            self.assertEqual(updated['health_level'], 'healthy')
            self.assertTrue(updated['conversation_ready'])

            reread = read_run_state(run_state_file, stable_required_runs=3)
            self.assertEqual(reread['health_level'], 'healthy')
            self.assertTrue(reread['conversation_ready'])

    def test_event_history_keeps_latest_entries(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            history_file = Path(temp_dir) / 'event-history.jsonl'
            append_event_history(history_file, {'status': 'healthy'}, keep=2)
            append_event_history(history_file, {'status': 'degraded'}, keep=2)
            append_event_history(history_file, {'status': 'failed'}, keep=2)

            events = read_event_history(history_file)
            self.assertEqual([event['status'] for event in events], ['degraded', 'failed'])

    def test_sibling_json_path_uses_same_stem(self) -> None:
        path = Path('/tmp/last-event.txt')
        self.assertEqual(sibling_json_path(path), Path('/tmp/last-event.json'))


if __name__ == '__main__':
    unittest.main()
