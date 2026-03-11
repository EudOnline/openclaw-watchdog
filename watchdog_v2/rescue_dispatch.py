from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from watchdog_v2.rescue_models import RescueAttempt, RescueContext, RescuePlan


@dataclass(eq=True)
class DispatchResult:
    executor_order: list[str] = field(default_factory=list)
    final_executor: str = ''
    installed_anything: bool = False
    attempts: list[RescueAttempt] = field(default_factory=list)
    plan: RescuePlan | None = None


class RescueDispatcher:
    def __init__(self, *, adapters: list[Any] | None = None) -> None:
        self.adapters = list(adapters or [])

    def dispatch(self, context: RescueContext) -> DispatchResult:
        result = DispatchResult(installed_anything=False)
        for adapter in self.adapters:
            if not adapter.is_available(context):
                result.attempts.append(RescueAttempt(executor=adapter.name, status='unavailable'))
                continue
            result.executor_order.append(adapter.name)
            try:
                plan = adapter.propose_plan(context)
            except Exception as exc:
                result.attempts.append(RescueAttempt(executor=adapter.name, status='error', error=str(exc)))
                continue
            if plan is None:
                result.attempts.append(RescueAttempt(executor=adapter.name, status='no-plan'))
                continue
            result.attempts.append(RescueAttempt(executor=adapter.name, status='plan-generated', plan_id=plan.plan_id))
            result.final_executor = adapter.name
            result.plan = plan
            return result
        if not result.final_executor and result.executor_order:
            result.final_executor = result.executor_order[-1]
        return result
