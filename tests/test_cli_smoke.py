import sys
import unittest
from unittest.mock import patch


class _EngineStub:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None


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
        with patch('openclaw_watchdog.cli.Config.load', return_value=config) as config_load:
            with patch('openclaw_watchdog.cli_commands.bootstrap_command.run', return_value=17) as run_command:
                with patch('openclaw_watchdog.cli.WatchdogEngine') as engine_type:
                    exit_code = main(['bootstrap', '--json'])

        self.assertEqual(exit_code, 17)
        config_load.assert_called_once()
        run_command.assert_called_once()
        called_args = run_command.call_args.kwargs
        self.assertIs(called_args['config'], config)
        engine_type.assert_not_called()

    def test_engine_commands_dispatch_through_command_owner_modules(self) -> None:
        from openclaw_watchdog.cli import main

        cases = [
            (['run-once'], 'openclaw_watchdog.cli_commands.run_once_command.run'),
            (['status'], 'openclaw_watchdog.cli_commands.status_command.run'),
            (['report'], 'openclaw_watchdog.cli_commands.report_command.run'),
            (['metrics'], 'openclaw_watchdog.cli_commands.metrics_command.run'),
            (['incidents', 'queue'], 'openclaw_watchdog.cli_commands.incidents_command.run'),
            (['maintenance', 'status'], 'openclaw_watchdog.cli_commands.maintenance_command.run'),
        ]

        for argv, target in cases:
            with self.subTest(argv=argv):
                with patch('openclaw_watchdog.cli.Config.load', return_value=object()):
                    with patch('openclaw_watchdog.cli.WatchdogEngine', return_value=_EngineStub()):
                        with patch(target, return_value=23) as run_command:
                            exit_code = main(argv)

                self.assertEqual(exit_code, 23)
                run_command.assert_called_once()


if __name__ == '__main__':
    unittest.main()
