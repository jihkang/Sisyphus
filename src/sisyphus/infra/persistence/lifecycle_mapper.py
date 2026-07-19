from __future__ import annotations

from collections.abc import Mapping

from ...conformance import summarize_task_conformance
from ...domain.lifecycle.models import (
    ConformanceState,
    GateSpec,
    LifecycleAction,
    LifecycleSnapshot,
    PlanStatus,
    PromotionState,
    SpecStatus,
    SubtaskConformance,
)
from ...gates import make_gate
from ...promotion_state import promotion_summary


_CONFORMANCE_ACTIONS = frozenset(
    {
        LifecycleAction.START_EXECUTION,
        LifecycleAction.VERIFY,
        LifecycleAction.CLOSE,
        LifecycleAction.EXECUTE_PROMOTION,
    }
)


class LifecycleRecordMapper:
    """Translate the legacy persisted task shape at the architecture boundary."""

    @staticmethod
    def to_domain(task: dict, *, action: LifecycleAction) -> LifecycleSnapshot:
        closed = _is_closed(task)
        inspect_transition_data = not closed or action == LifecycleAction.CLOSE
        conformance = ConformanceState()
        promotion = PromotionState()

        if inspect_transition_data and action in _CONFORMANCE_ACTIONS:
            conformance = _map_conformance(summarize_task_conformance(task))
        if inspect_transition_data and action == LifecycleAction.CLOSE:
            promotion = _map_promotion(promotion_summary(task))

        return LifecycleSnapshot(
            current_phase=_optional_phase(task.get("workflow_phase")),
            closed=closed,
            plan_status=_plan_status(task.get("plan_status")),
            plan_review_round=int(task.get("plan_review_round", 0)),
            max_plan_review_rounds=int(task.get("max_plan_review_rounds", 3)),
            spec_status=_spec_status(task.get("spec_status")),
            verify_status=str(task.get("verify_status") or ""),
            conformance=conformance,
            promotion=promotion,
        )

    @staticmethod
    def gate_to_record(gate: GateSpec) -> dict:
        return make_gate(
            gate.code,
            gate.message,
            gate.source,
            blocking=gate.blocking,
            severity=gate.severity,
            checkpoint_type=gate.checkpoint_type,
            subtask_id=gate.subtask_id,
        )


def _map_conformance(summary: Mapping[str, object]) -> ConformanceState:
    subtasks = summary.get("subtasks")
    mapped_subtasks: list[SubtaskConformance] = []
    if isinstance(subtasks, list):
        for item in subtasks:
            if not isinstance(item, Mapping):
                continue
            mapped_subtasks.append(
                SubtaskConformance(
                    subtask_id=_optional_text(item.get("id")),
                    status=str(item.get("status") or "green"),
                    unresolved_warning_count=int(item.get("unresolved_warning_count", 0)),
                    last_checkpoint_type=_optional_text(item.get("last_checkpoint_type")),
                )
            )
    return ConformanceState(
        status=str(summary.get("status") or "green"),
        unresolved_warning_count=int(summary.get("unresolved_warning_count", 0)),
        last_checkpoint_type=_optional_text(summary.get("last_checkpoint_type")),
        subtasks=tuple(mapped_subtasks),
    )


def _map_promotion(summary: Mapping[str, object]) -> PromotionState:
    return PromotionState(
        required=bool(summary.get("required")),
        status=_optional_text(summary.get("status")),
    )


def _plan_status(value: object) -> PlanStatus:
    try:
        return PlanStatus(str(value or PlanStatus.APPROVED.value))
    except ValueError:
        return PlanStatus.APPROVED


def _spec_status(value: object) -> SpecStatus:
    try:
        return SpecStatus(str(value or SpecStatus.FROZEN.value))
    except ValueError:
        return SpecStatus.FROZEN


def _optional_text(value: object) -> str | None:
    if value in (None, ""):
        return None
    return str(value)


def _optional_phase(value: object) -> str | None:
    normalized = str(value or "").strip()
    return normalized or None


def _is_closed(task: Mapping[str, object]) -> bool:
    return str(task.get("status") or "").strip().lower() == "closed" or bool(task.get("closed_at"))


__all__ = ["LifecycleRecordMapper"]
