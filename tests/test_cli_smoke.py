import sys
import unittest

@unittest.skipUnless(sys.version_info >= (3, 11), 'cli import requires Python 3.11+')
class CliSmokeTest(unittest.TestCase):
    @staticmethod
    def _build_parser():
        from watchdog_v2.cli import build_parser

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


if __name__ == '__main__':
    unittest.main()
