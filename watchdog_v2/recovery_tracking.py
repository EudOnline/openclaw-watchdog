from __future__ import annotations


def reset(ctx, *, stable_required_runs: int) -> None:
    ctx.recovery_steps = []
    ctx.last_recovery_strategy = 'none'
    ctx.last_recovery_action_count = 0
    ctx.last_recovery_restored_conversation = False
    ctx.rescue_attempt_count = 0
    ctx.rescue_executor_selected = ''
    ctx.rescue_plan_generated = False
    ctx.rescue_plan_source = ''
    ctx.rescue_plan_id = ''
    ctx.rescue_plan_status = 'not-run'
    ctx.rescue_tier = 'none'
    ctx.case_ingest_result = 'not-run'
    ctx.candidate_rule_status = 'none'
    ctx.rescue_attempt_order = []
    ctx.rescue_rejected_executors = []
    ctx.rescue_learning_summary = 'not-run / none'
    ctx.rescue_mutation_scope = []
    ctx.rollback_candidate_used = ''
    ctx.rollback_reason = ''
    ctx.config_drift_detected = False
    ctx.survival_mode_active = False
    ctx.survival_mode_reason = ''
    ctx.survival_mode_since = ''
    ctx.survival_mode_summary = ''
    ctx.survival_mode_actions = []
    ctx.survival_mode_disabled_features = []
    ctx.survival_mode_config_file = ''
    ctx.survival_mode_sticky = False
    ctx.survival_mode_sticky_reason = ''
    ctx.survival_mode_exit_ready = False
    ctx.survival_mode_exit_policy = 'none'
    ctx.survival_mode_exit_blockers = []
    ctx.survival_mode_stable_ready_runs = 0
    ctx.survival_mode_stable_required_runs = stable_required_runs
    ctx.survival_mode_manual_clear_required = False
    ctx.survival_mode_config_changed_away = False
    ctx.survival_mode_last_exit_at = ''
    ctx.survival_mode_last_exit_reason = ''
    ctx.survival_mode_last_exit_kind = ''
    ctx.survival_mode_last_exit_summary = ''
    ctx.drift_scope = []
    ctx.drift_since_last_good = ''
    ctx.drift_summary = ''
    ctx.latest_probe = {}


def record_step(ctx, step: str, outcome: str, detail: str = '') -> None:
    token = f'{step}:{outcome}'
    if detail:
        token = f'{token}({detail})'
    ctx.recovery_steps.append(token)
    if outcome not in {'skipped', 'diagnosed', 'not-applicable'}:
        ctx.last_recovery_action_count += 1


def path_text(ctx) -> str:
    return ' -> '.join(ctx.recovery_steps) if ctx.recovery_steps else 'none'


def finalize(ctx, *, strategy: str, restored_conversation: bool) -> None:
    ctx.last_recovery_strategy = strategy or 'none'
    ctx.last_recovery_restored_conversation = bool(restored_conversation)
