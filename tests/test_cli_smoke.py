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

    def test_cli_module_no_longer_defines_text_output_helpers(self) -> None:
        from openclaw_watchdog import cli

        for name in (
            '_print_json',
            '_print_run_once',
            '_print_check',
            '_print_status_summary',
            '_print_report',
            '_print_metrics',
            '_print_status',
            '_print_incidents_list',
            '_print_incident_detail',
            '_print_incident_queue',
            '_print_incident_timeline',
            '_print_maintenance',
            '_print_bootstrap',
        ):
            with self.subTest(name=name):
                self.assertFalse(hasattr(cli, name))

    def test_cli_dispatch_wires_output_helpers_from_owner_module(self) -> None:
        from openclaw_watchdog import cli
        from openclaw_watchdog.cli import main

        cli_output = type(
            'CliOutputStub',
            (),
            {
                'print_json': object(),
                'print_bootstrap': object(),
                'print_run_once': object(),
                'print_check': object(),
                'print_status_summary': object(),
                'print_status': object(),
                'print_report': object(),
                'print_metrics': object(),
                'print_incidents_list': object(),
                'print_incident_detail': object(),
                'print_incident_queue': object(),
                'print_incident_timeline': object(),
                'print_maintenance': object(),
            },
        )()

        cases = [
            (
                ['bootstrap', '--json'],
                'openclaw_watchdog.cli_commands.bootstrap_command.run',
                {
                    'json_printer': cli_output.print_json,
                    'bootstrap_printer': cli_output.print_bootstrap,
                },
                False,
            ),
            (
                ['run-once'],
                'openclaw_watchdog.cli_commands.run_once_command.run',
                {
                    'json_printer': cli_output.print_json,
                    'run_once_printer': cli_output.print_run_once,
                    'check_printer': cli_output.print_check,
                },
                True,
            ),
            (
                ['status'],
                'openclaw_watchdog.cli_commands.status_command.run',
                {
                    'json_printer': cli_output.print_json,
                    'summary_printer': cli_output.print_status_summary,
                    'status_printer': cli_output.print_status,
                },
                True,
            ),
            (
                ['incidents', 'queue'],
                'openclaw_watchdog.cli_commands.incidents_command.run',
                {
                    'json_printer': cli_output.print_json,
                    'incidents_list_printer': cli_output.print_incidents_list,
                    'incident_detail_printer': cli_output.print_incident_detail,
                    'incident_queue_printer': cli_output.print_incident_queue,
                    'incident_timeline_printer': cli_output.print_incident_timeline,
                },
                True,
            ),
            (
                ['maintenance', 'status'],
                'openclaw_watchdog.cli_commands.maintenance_command.run',
                {
                    'json_printer': cli_output.print_json,
                    'maintenance_printer': cli_output.print_maintenance,
                },
                True,
            ),
        ]

        for argv, target, expected_kwargs, uses_engine in cases:
            with self.subTest(argv=argv):
                with patch.object(cli, 'cli_output', cli_output, create=True):
                    with patch('openclaw_watchdog.cli.Config.load', return_value=object()):
                        with patch(target, return_value=29) as run_command:
                            if uses_engine:
                                with patch('openclaw_watchdog.cli.WatchdogEngine', return_value=_EngineStub()):
                                    exit_code = main(argv)
                            else:
                                with patch('openclaw_watchdog.cli.WatchdogEngine') as engine_type:
                                    exit_code = main(argv)
                                    engine_type.assert_not_called()

                self.assertEqual(exit_code, 29)
                called_kwargs = run_command.call_args.kwargs
                for key, expected in expected_kwargs.items():
                    self.assertIs(called_kwargs[key], expected)


if __name__ == '__main__':
    unittest.main()
