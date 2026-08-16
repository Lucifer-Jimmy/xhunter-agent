"""Minimal deterministic planner used until a model-backed planner is added."""

from xhunter.contracts.planning import PlanningContext, PlanningDecision


class RulePlanner:
    """Do not invent tasks when pending work already exists."""

    async def plan(self, context: PlanningContext) -> PlanningDecision:
        if context.pending_tasks:
            return PlanningDecision(rationale="pending tasks already exist")
        return PlanningDecision(rationale="no rule-based task generation configured")
