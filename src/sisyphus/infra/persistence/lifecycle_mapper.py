from __future__ import annotations

from collections.abc import Mapping

from ...application.planning_records import gate_spec_to_record
from ...domain.lifecycle.models import (
    ConformanceState,
    GateSpec,
    LifecycleAction,
    LifecycleSnapshot,
    PromotionState,
    SubtaskConformance,
)
from ...domain.planning.models import normalize_plan_status, normalize_spec_status
from ...domain.promotion.state import promotion_summary
from ...domain.task.conformance import (
    CONFORMANCE_GREEN,
    CONFORMANCE_RED,
    CONFORMANCE_YELLOW,
    ensure_task_conformance_defaults,
    normalize_conformance_status,
)
from ...domain.task.design import ensure_task_design_defaults
from ...shared.clock import utc_now


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
            conformance = _map_conformance(task)
        if inspect_transition_data and action == LifecycleAction.CLOSE:
            promotion = _map_promotion(promotion_summary(task))

        return LifecycleSnapshot(
            current_phase=_optional_phase(task.get("workflow_phase")),
            closed=closed,
            plan_status=normalize_plan_status(task.get("plan_status")),
            plan_review_round=int(task.get("plan_review_round", 0)),
            max_plan_review_rounds=int(task.get("max_plan_review_rounds", 3)),
            spec_status=normalize_spec_status(task.get("spec_status")),
            verify_status=str(task.get("verify_status") or ""),
            conformance=conformance,
            promotion=promotion,
        )

    @staticmethod
    def gate_to_record(gate: GateSpec) -> dict:
        return gate_spec_to_record(gate, created_at=utc_now())


def _map_conformance(task: dict) -> ConformanceState:
    ensure_task_conformance_defaults(task)
    ensure_task_design_defaults(task)
    record = task["conformance"]
    mapped_subtasks: list[SubtaskConformance] = []
    for subtask in task.get("subtasks", []):
        if not isinstance(subtask, Mapping):
            continue
        subtask_record = subtask.get("conformance")
        if not isinstance(subtask_record, Mapping):
            continue
        mapped_subtasks.append(
            SubtaskConformance(
                subtask_id=_optional_text(subtask.get("id")),
                status=normalize_conformance_status(subtask_record.get("status")),
                unresolved_warning_count=int(subtask_record.get("unresolved_warning_count", 0)),
                last_checkpoint_type=_optional_text(subtask_record.get("last_checkpoint_type")),
            )
        )
    status = _aggregate_conformance_status(
        normalize_conformance_status(record.get("status")),
        tuple(item.status for item in mapped_subtasks),
    )
    return ConformanceState(
        status=status,
        unresolved_warning_count=int(record.get("unresolved_warning_count", 0)),
        last_checkpoint_type=_optional_text(record.get("last_checkpoint_type")),
        subtasks=tuple(mapped_subtasks),
    )


def _aggregate_conformance_status(task_status: str, subtask_statuses: tuple[str, ...]) -> str:
    statuses = (task_status, *subtask_statuses)
    if CONFORMANCE_RED in statuses:
        return CONFORMANCE_RED
    if CONFORMANCE_YELLOW in statuses:
        return CONFORMANCE_YELLOW
    return CONFORMANCE_GREEN


def _map_promotion(summary: Mapping[str, object]) -> PromotionState:
    return PromotionState(
        required=bool(summary.get("required")),
        status=_optional_text(summary.get("status")),
    )


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
