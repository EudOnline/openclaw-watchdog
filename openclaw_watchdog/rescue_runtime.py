from __future__ import annotations

from typing import Any

from openclaw_watchdog import executor_registry, rescue_context_builder


def build_rescue_adapters(engine, context) -> list[Any]:
    from openclaw_watchdog.learning import LearningStore
    from openclaw_watchdog.rescue_agents.claude_code_adapter import ClaudeCodeAdapter
    from openclaw_watchdog.rescue_agents.codex_adapter import CodexAdapter
    from openclaw_watchdog.rescue_agents.gemini_cli_adapter import GeminiCliAdapter
    from openclaw_watchdog.rescue_agents.litellm_agent import LiteLLMSpecialistAgent
    from openclaw_watchdog.rescue_agents.opencode_adapter import OpenCodeAdapter
    from openclaw_watchdog.rescue_agents.rule_agent import RuleBasedRescueAgent

    available = set(getattr(context, 'available_executors', ()))
    config = engine.config
    learning_store = LearningStore(root=config.watchdog_rescue_knowledge_root)
    adapters_by_name = {
        'codex': CodexAdapter(
            available='codex' in available,
            command=executor_registry.rescue_command(config, 'codex'),
            runner=engine.run_command,
            timeout_seconds=executor_registry.timeout_seconds(config, 'codex', default=120),
            cwd=executor_registry.workdir(config, 'codex'),
        ),
        'claude-code': ClaudeCodeAdapter(
            available='claude-code' in available,
            command=executor_registry.rescue_command(config, 'claude-code'),
            runner=engine.run_command,
            timeout_seconds=executor_registry.timeout_seconds(config, 'claude-code', default=120),
            cwd=executor_registry.workdir(config, 'claude-code'),
        ),
        'gemini-cli': GeminiCliAdapter(
            available='gemini-cli' in available,
            command=executor_registry.rescue_command(config, 'gemini-cli'),
            runner=engine.run_command,
            timeout_seconds=executor_registry.timeout_seconds(config, 'gemini-cli', default=120),
            cwd=executor_registry.workdir(config, 'gemini-cli'),
        ),
        'opencode': OpenCodeAdapter(
            available='opencode' in available,
            command=executor_registry.rescue_command(config, 'opencode'),
            runner=engine.run_command,
            timeout_seconds=executor_registry.timeout_seconds(config, 'opencode', default=120),
            cwd=executor_registry.workdir(config, 'opencode'),
        ),
        'litellm': LiteLLMSpecialistAgent(
            config=config,
            client=rescue_context_builder.build_litellm_client(config),
        ),
        'rule-agent': RuleBasedRescueAgent(rule_store=learning_store),
    }
    return [adapters_by_name[name] for name in executor_registry.configured_priority(config) if name in adapters_by_name]


def dispatch_rescue(engine, context):
    from openclaw_watchdog.rescue_dispatch import RescueDispatcher

    return RescueDispatcher(adapters=build_rescue_adapters(engine, context)).dispatch(context)


def execute_rescue_plan(engine, plan, *, executor: str):
    from openclaw_watchdog.rescue_actions import RescueActionExecutor
    from openclaw_watchdog.rescue_models import RescueResult

    result = RescueActionExecutor(config=engine.config, engine=engine).apply_plan(plan)
    return RescueResult(
        status=result.status,
        executor=executor,
        plan_id=plan.plan_id,
        rollback_performed=result.rollback_performed,
        details=dict(result.details),
    )
