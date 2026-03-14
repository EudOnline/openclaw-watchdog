import unittest

from openclaw_watchdog.rescue_models import RescueAction, RescueContext, RescuePlan, RescueResult


class RescueModelTests(unittest.TestCase):
    def test_plan_rejects_unknown_action_type(self) -> None:
        with self.assertRaises(ValueError):
            RescueAction(kind='run_shell', params={'cmd': 'rm -rf /'})

    def test_plan_requires_validation_steps_for_mutation(self) -> None:
        with self.assertRaises(ValueError):
            RescuePlan(
                plan_id='plan-1',
                diagnosis='bad config',
                actions=[RescueAction(kind='update_openclaw_config', params={'file': 'state/openclaw.json'})],
                validations=[],
            )

    def test_plan_rejects_unimplemented_compatibility_actions(self) -> None:
        for action_name in (
            'validate_conversation',
            'collect_incident',
            'disable_optional_channel',
            'disable_optional_extension',
            'switch_to_minimal_channel_set',
        ):
            with self.subTest(action=action_name):
                with self.assertRaises(ValueError):
                    RescueAction(kind=action_name, params={})

    def test_context_and_result_round_trip(self) -> None:
        context = RescueContext(
            incident_id='incident-1',
            health_level='failed',
            available_executors=('codex', 'litellm', 'rule-agent'),
            editable_paths=('~/.openclaw/openclaw.json',),
            editable_keys=('channels.qqbot.enabled',),
        )
        result = RescueResult(
            status='recovered',
            executor='rule-agent',
            plan_id='plan-1',
            rollback_performed=False,
        )

        self.assertEqual(RescueContext.from_dict(context.to_dict()), context)
        self.assertEqual(RescueResult.from_dict(result.to_dict()), result)


if __name__ == '__main__':
    unittest.main()
