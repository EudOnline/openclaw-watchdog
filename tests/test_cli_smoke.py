import sys
import unittest
from unittest.mock import patch

@unittest.skipUnless(sys.version_info >= (3, 11), 'cli import requires Python 3.11+')
class CliSmokeTest(unittest.TestCase):
    @staticmethod
    def _build_parser():
        from openclaw_watchdog.cli import build_parser

        return build_parser()

    def test_parses_status_summary(self) -> None:
        parser = self._build_parser()
        args = parser.parse_args(['status', '--summary'])

        self.assertEqual(args.command, 'status')
        self.assertTrue(args.summary)

    def test_parses_incidents_queue_limit(self) -> None:
        parser = self._build_parser()
        args = parser.parse_args(['incidents', 'queue', '--limit', '7'])

        self.assertEqual(args.command, 'incidents')
        self.assertEqual(args.incidents_command, 'queue')
        self.assertEqual(args.limit, 7)

    def test_parses_report_message(self) -> None:
        parser = self._build_parser()
        args = parser.parse_args(['report', '--message'])

        self.assertEqual(args.command, 'report')
        self.assertTrue(args.message)

    def test_parser_mentions_operator_quick_path(self) -> None:
        parser = self._build_parser()

        self.assertIn('Operator quick path', parser.epilog)
        self.assertIn('status --summary', parser.epilog)

    def test_parser_exposes_stable_top_level_commands(self) -> None:
        parser = self._build_parser()
        subparsers_action = next(action for action in parser._actions if getattr(action, 'choices', None))

        self.assertTrue(
            {
                'run-once',
                'check',
                'detect',
                'status',
                'report',
                'metrics',
                'incidents',
                'bootstrap',
                'maintenance',
            }.issubset(subparsers_action.choices)
        )
        self.assertNotIn('provision', subparsers_action.choices)

    def test_bootstrap_parser_rejects_legacy_install_flag(self) -> None:
        parser = self._build_parser()

        with self.assertRaises(SystemExit):
            parser.parse_args(['bootstrap', '--install-openclaw'])

    def test_bootstrap_dispatches_bootstrap_flow_without_legacy_aliases(self) -> None:
        from openclaw_watchdog.cli import main

        config = object()
        outcome = type('BootstrapOutcomeStub', (), {'exit_code': 17, 'payload': {'state': 'attention'}})()
        with patch('openclaw_watchdog.cli.Config.load', return_value=config) as config_load:
            with patch('openclaw_watchdog.cli.Bootstrapper') as bootstrapper:
                with patch('openclaw_watchdog.cli.WatchdogEngine') as engine_type:
                    with patch('openclaw_watchdog.cli._print_json'):
                        bootstrapper.return_value.run.return_value = outcome

                        exit_code = main(['bootstrap', '--json'])

        self.assertEqual(exit_code, 17)
        config_load.assert_called_once()
        bootstrapper.assert_called_once_with(config)
        bootstrapper.return_value.run.assert_called_once_with()
        engine_type.assert_not_called()


if __name__ == '__main__':
    unittest.main()
