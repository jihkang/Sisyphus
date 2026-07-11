from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .lifecycle_rules import evaluate_transition
from .lifecycle_state import LifecycleAction


class ActionRiskLevel(str, Enum):
    READ_ONLY = "read_only"
    LOW_RISK_WRITE = "low_risk_write"
    REVIEW_GATED = "review_gated"
    HUMAN_ONLY = "human_only"


@dataclass(frozen=True, slots=True)
class ActionSpec:
    name: str
    risk: ActionRiskLevel
    allowed_for_policy: bool
    requires_human: bool
    mutates_state: bool
    description: str
    lifecycle_action: LifecycleAction | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "risk": self.risk.value,
            "allowed_for_policy": self.allowed_for_policy,
            "requires_human": self.requires_human,
            "mutates_state": self.mutates_state,
            "description": self.description,
            "lifecycle_action": self.lifecycle_action.value if self.lifecycle_action else None,
        }


ACTION_REGISTRY: dict[str, ActionSpec] = {
    "sisyphus.get_task": ActionSpec(
        name="sisyphus.get_task",
        risk=ActionRiskLevel.READ_ONLY,
        allowed_for_policy=True,
        requires_human=False,
        mutates_state=False,
        description="Read a task record.",
    ),
    "sisyphus.read_resource": ActionSpec(
        name="sisyphus.read_resource",
        risk=ActionRiskLevel.READ_ONLY,
        allowed_for_policy=True,
        requires_human=False,
        mutates_state=False,
        description="Read a Sisyphus MCP resource.",
    ),
    "sisyphus.search": ActionSpec(
        name="sisyphus.search",
        risk=ActionRiskLevel.READ_ONLY,
        allowed_for_policy=True,
        requires_human=False,
        mutates_state=False,
        description="Search repository-local task and artifact evidence.",
    ),
    "sisyphus.context_build": ActionSpec(
        name="sisyphus.context_build",
        risk=ActionRiskLevel.READ_ONLY,
        allowed_for_policy=True,
        requires_human=False,
        mutates_state=False,
        description="Build a ContextPack from repository-local search results.",
    ),
    "sisyphus.list_agents": ActionSpec(
        name="sisyphus.list_agents",
        risk=ActionRiskLevel.READ_ONLY,
        allowed_for_policy=True,
        requires_human=False,
        mutates_state=False,
        description="List tracked agents for a repository or task.",
    ),
    "sisyphus.plan_revise": ActionSpec(
        name="sisyphus.plan_revise",
        risk=ActionRiskLevel.LOW_RISK_WRITE,
        allowed_for_policy=True,
        requires_human=False,
        mutates_state=True,
        description="Revise a task plan after review feedback.",
        lifecycle_action=LifecycleAction.REVISE_PLAN,
    ),
    "sisyphus.subtasks_generate": ActionSpec(
        name="sisyphus.subtasks_generate",
        risk=ActionRiskLevel.LOW_RISK_WRITE,
        allowed_for_policy=True,
        requires_human=False,
        mutates_state=True,
        description="Generate subtasks from a frozen spec and test strategy.",
        lifecycle_action=LifecycleAction.GENERATE_SUBTASKS,
    ),
    "sisyphus.verify_task": ActionSpec(
        name="sisyphus.verify_task",
        risk=ActionRiskLevel.LOW_RISK_WRITE,
        allowed_for_policy=True,
        requires_human=False,
        mutates_state=True,
        description="Run verification and record results.",
        lifecycle_action=LifecycleAction.VERIFY,
    ),
    "sisyphus.plan_request_changes": ActionSpec(
        name="sisyphus.plan_request_changes",
        risk=ActionRiskLevel.REVIEW_GATED,
        allowed_for_policy=False,
        requires_human=True,
        mutates_state=True,
        description="Request plan changes after review.",
        lifecycle_action=LifecycleAction.REQUEST_PLAN_CHANGES,
    ),
    "sisyphus.plan_approve": ActionSpec(
        name="sisyphus.plan_approve",
        risk=ActionRiskLevel.REVIEW_GATED,
        allowed_for_policy=False,
        requires_human=True,
        mutates_state=True,
        description="Approve a task plan.",
        lifecycle_action=LifecycleAction.APPROVE_PLAN,
    ),
    "sisyphus.spec_freeze": ActionSpec(
        name="sisyphus.spec_freeze",
        risk=ActionRiskLevel.REVIEW_GATED,
        allowed_for_policy=False,
        requires_human=True,
        mutates_state=True,
        description="Freeze a task spec after review.",
        lifecycle_action=LifecycleAction.FREEZE_SPEC,
    ),
    "sisyphus.close_task": ActionSpec(
        name="sisyphus.close_task",
        risk=ActionRiskLevel.REVIEW_GATED,
        allowed_for_policy=False,
        requires_human=True,
        mutates_state=True,
        description="Close a verified task.",
        lifecycle_action=LifecycleAction.CLOSE,
    ),
    "sisyphus.record_merged_pr": ActionSpec(
        name="sisyphus.record_merged_pr",
        risk=ActionRiskLevel.HUMAN_ONLY,
        allowed_for_policy=False,
        requires_human=True,
        mutates_state=True,
        description="Record a merged pull request receipt.",
        lifecycle_action=LifecycleAction.RECORD_MERGED_PR,
    ),
    "sisyphus.execute_promotion": ActionSpec(
        name="sisyphus.execute_promotion",
        risk=ActionRiskLevel.HUMAN_ONLY,
        allowed_for_policy=False,
        requires_human=True,
        mutates_state=True,
        description="Commit, push, and open a pull request for a task branch.",
        lifecycle_action=LifecycleAction.EXECUTE_PROMOTION,
    ),
}


def allowed_policy_actions(task: dict) -> tuple[str, ...]:
    return tuple(
        name
        for name, spec in sorted(ACTION_REGISTRY.items())
        if spec.allowed_for_policy and _environment_allows(task, spec)
    )


def forbidden_policy_actions(task: dict) -> tuple[dict[str, object], ...]:
    forbidden: list[dict[str, object]] = []
    for name, spec in sorted(ACTION_REGISTRY.items()):
        transition = None
        if spec.lifecycle_action is not None:
            transition = evaluate_transition(task, spec.lifecycle_action)
        if spec.allowed_for_policy and (transition is None or transition.allowed):
            continue

        reason = "Action is outside the policy-safe action set."
        gates: list[dict] = []
        if transition is not None and not transition.allowed:
            reason = transition.reason
            gates = list(transition.gates)
        elif spec.requires_human:
            reason = "Action requires human review or operator judgment."

        forbidden.append(
            {
                "action": name,
                "risk": spec.risk.value,
                "requires_human": spec.requires_human,
                "reason": reason,
                "gates": gates,
            }
        )
    return tuple(forbidden)


def _environment_allows(task: dict, spec: ActionSpec) -> bool:
    if spec.lifecycle_action is None:
        return True
    return evaluate_transition(task, spec.lifecycle_action).allowed


__all__ = [
    "ACTION_REGISTRY",
    "ActionRiskLevel",
    "ActionSpec",
    "allowed_policy_actions",
    "forbidden_policy_actions",
]
