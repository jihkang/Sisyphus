from __future__ import annotations

from dataclasses import dataclass

from ...domain.lifecycle import LifecycleAction
from ...domain.planning.models import PlanStatus, SpecStatus
from ...domain.task.design import ensure_task_design_defaults, freeze_design_anchor
from ..planning_records import (
    collect_plan_gate_records,
    collect_spec_gate_records,
    current_plan_status,
    current_spec_status,
    dedupe_gate_records,
    record_planning_lifecycle_transition,
)
from ..ports.clock import ClockPort
from ..ports.planning import DesignConformancePort, PlanningDocumentPort, SpecValidationPort
from ..ports.workflow import ManualInterventionPort, TaskRecord, TaskRecordPort
from ..results.planning import PlanReviewOutcome, SpecFreezeOutcome, SubtaskGenerationOutcome


PLAN_PENDING_REVIEW = PlanStatus.PENDING_REVIEW.value
PLAN_APPROVED = PlanStatus.APPROVED.value
PLAN_CHANGES_REQUESTED = PlanStatus.CHANGES_REQUESTED.value
PLAN_REVIEW_LIMIT_REACHED = "PLAN_REVIEW_LIMIT_REACHED"
PLAN_STATUSES = {PLAN_PENDING_REVIEW, PLAN_APPROVED, PLAN_CHANGES_REQUESTED}
SPEC_DRAFT = SpecStatus.DRAFT.value
SPEC_FROZEN = SpecStatus.FROZEN.value
SPEC_STATUSES = {SPEC_DRAFT, SPEC_FROZEN}


@dataclass(slots=True)
class PlanningService:
    tasks: TaskRecordPort
    documents: PlanningDocumentPort
    validation: SpecValidationPort
    design_conformance: DesignConformancePort
    interventions: ManualInterventionPort
    clock: ClockPort

    def approve_plan(
        self,
        task_id: str,
        *,
        reviewer: str,
        notes: str | None,
    ) -> PlanReviewOutcome:
        task = self.tasks.load(task_id)
        _ensure_plan_fields(task)
        transition = record_planning_lifecycle_transition(
            task,
            LifecycleAction.APPROVE_PLAN,
            gate_sources={"lifecycle"},
            created_at=self.clock.now(),
        )
        if not transition.allowed:
            task["status"] = "blocked"
            task["stage"] = "plan_review"
            self.tasks.save(task)
            return _plan_outcome(task)

        task = self.documents.sync_strategy(task_id, task)
        validation_gates = self.validation.collect_gates(
            task_id,
            task,
            action="plan approval",
            refresh=True,
        )
        if validation_gates:
            task["gates"] = dedupe_gate_records(
                [
                    gate
                    for gate in task.get("gates", [])
                    if gate.get("source") not in {"plan", "spec_validation"}
                ]
                + list(validation_gates)
            )
            task["status"] = "blocked"
            task["stage"] = "plan_review"
            task["workflow_phase"] = "plan_revision"
            self.tasks.save(task)
            return _plan_outcome(task)

        task["plan_status"] = PLAN_APPROVED
        task["plan_reviewed_at"] = self.clock.now()
        task["plan_reviewed_by"] = reviewer.strip() or "operator"
        task["plan_review_notes"] = notes
        task["workflow_phase"] = "spec_drafting"
        task["gates"] = [
            gate
            for gate in task.get("gates", [])
            if gate.get("source") not in {"plan", "spec_validation"}
        ]
        _append_review_history(
            task,
            action="approve",
            actor=str(task["plan_reviewed_by"]),
            notes=notes,
            timestamp=self.clock.now(),
        )
        _restore_task_status_after_plan_gate(task)
        self.tasks.save(task)
        self.interventions.required(
            task_id=str(task["id"]),
            reason="spec_freeze_required",
            workflow_phase="spec_drafting",
            status=str(task.get("status") or ""),
            detail="plan approval completed and the task now awaits spec freeze",
        )
        return _plan_outcome(task)

    def request_changes(
        self,
        task_id: str,
        *,
        reviewer: str,
        notes: str | None,
    ) -> PlanReviewOutcome:
        task = self.tasks.load(task_id)
        _ensure_plan_fields(task)
        transition = record_planning_lifecycle_transition(
            task,
            LifecycleAction.REQUEST_PLAN_CHANGES,
            gate_sources={"lifecycle"},
            created_at=self.clock.now(),
        )
        if not transition.allowed:
            task["status"] = "blocked"
            task["stage"] = "plan_review"
            self.tasks.save(task)
            return _plan_outcome(task)

        task["plan_status"] = PLAN_CHANGES_REQUESTED
        task["plan_review_round"] = int(task.get("plan_review_round", 0)) + 1
        task["plan_reviewed_at"] = self.clock.now()
        task["plan_reviewed_by"] = reviewer.strip() or "operator"
        task["plan_review_notes"] = notes
        task["workflow_phase"] = (
            "needs_user_input"
            if int(task["plan_review_round"]) >= int(task.get("max_plan_review_rounds", 3))
            else "plan_revision"
        )
        task["gates"] = dedupe_gate_records(
            [
                gate
                for gate in task.get("gates", [])
                if gate.get("source") not in {"plan", "spec_validation"}
            ]
            + collect_plan_gate_records(
                task,
                action="execution",
                created_at=self.clock.now(),
            )
        )
        _append_review_history(
            task,
            action="request_changes",
            actor=str(task["plan_reviewed_by"]),
            notes=notes,
            timestamp=self.clock.now(),
        )
        task["status"] = "blocked"
        task["stage"] = "plan_review"
        self.tasks.save(task)
        self.interventions.required(
            task_id=str(task["id"]),
            reason="plan_changes_requested",
            workflow_phase=str(task.get("workflow_phase") or ""),
            status=str(task.get("status") or ""),
            detail="plan review requested changes before execution can continue",
        )
        return _plan_outcome(task)

    def revise_plan(
        self,
        task_id: str,
        *,
        author: str,
        notes: str | None,
    ) -> PlanReviewOutcome:
        task = self.tasks.load(task_id)
        _ensure_plan_fields(task)
        transition = record_planning_lifecycle_transition(
            task,
            LifecycleAction.REVISE_PLAN,
            gate_sources={"plan", "lifecycle"},
            created_at=self.clock.now(),
        )
        if not transition.allowed:
            task["status"] = "blocked"
            task["stage"] = "plan_review"
            task["workflow_phase"] = "plan_revision"
            self.tasks.save(task)
            return _plan_outcome(task)

        task["plan_status"] = PLAN_PENDING_REVIEW
        task["plan_reviewed_at"] = self.clock.now()
        task["plan_reviewed_by"] = author.strip() or "operator"
        task["plan_review_notes"] = notes
        task["workflow_phase"] = "plan_in_review"
        task["gates"] = [
            gate
            for gate in task.get("gates", [])
            if gate.get("source") not in {"plan", "spec_validation"}
        ]
        _append_review_history(
            task,
            action="revise",
            actor=str(task["plan_reviewed_by"]),
            notes=notes,
            timestamp=self.clock.now(),
        )
        _restore_task_status_after_plan_gate(task)
        task["stage"] = "plan_review"
        self.tasks.save(task)
        self.interventions.required(
            task_id=str(task["id"]),
            reason="plan_review_required",
            workflow_phase="plan_in_review",
            status=str(task.get("status") or ""),
            detail="a revised plan now awaits another review decision",
        )
        return _plan_outcome(task)

    def enforce_plan_approved(self, task_id: str, *, action: str) -> tuple[bool, TaskRecord]:
        task = self.tasks.load(task_id)
        _ensure_plan_fields(task)
        plan_gates = collect_plan_gate_records(
            task,
            action=action,
            created_at=self.clock.now(),
        )
        task["gates"] = dedupe_gate_records(
            [gate for gate in task.get("gates", []) if gate.get("source") != "plan"]
            + plan_gates
        )
        if plan_gates:
            task["status"] = "blocked"
            task["stage"] = "plan_review"
            self.tasks.save(task)
            return False, task
        _restore_task_status_after_plan_gate(task)
        self.tasks.save(task)
        return True, task

    def freeze_spec(
        self,
        task_id: str,
        *,
        reviewer: str,
        notes: str | None,
    ) -> SpecFreezeOutcome:
        task = self.tasks.load(task_id)
        _ensure_plan_fields(task)
        _ensure_spec_fields(task)
        task = self.documents.sync_strategy(task_id, task)
        task["plan_status"] = current_plan_status(task)
        transition = record_planning_lifecycle_transition(
            task,
            LifecycleAction.FREEZE_SPEC,
            gate_sources={"plan", "spec", "lifecycle"},
            created_at=self.clock.now(),
        )
        if not transition.allowed:
            task["status"] = "blocked"
            task["stage"] = "plan_review"
            task["workflow_phase"] = "needs_user_input"
            self.tasks.save(task)
            return _freeze_outcome(task)

        validation_gates = self.validation.collect_gates(
            task_id,
            task,
            action="spec freeze",
            refresh=True,
        )
        if validation_gates:
            task["gates"] = dedupe_gate_records(
                [
                    gate
                    for gate in task.get("gates", [])
                    if gate.get("source") != "spec_validation"
                ]
                + list(validation_gates)
            )
            task["status"] = "blocked"
            task["stage"] = "spec"
            task["workflow_phase"] = "spec_in_review"
            self.tasks.save(task)
            return _freeze_outcome(task)

        task["gates"] = [
            gate for gate in task.get("gates", []) if gate.get("source") != "spec_validation"
        ]
        task["spec_status"] = SPEC_FROZEN
        task["spec_frozen_at"] = self.clock.now()
        task["spec_reviewed_by"] = reviewer.strip() or "operator"
        task["spec_review_notes"] = notes
        freeze_design_anchor(task, frozen_at=str(task["spec_frozen_at"]))
        self.design_conformance.mark_design_anchor(
            task,
            source="planning.freeze_task_spec",
        )
        task["workflow_phase"] = "subtask_planning"
        _restore_task_status_after_plan_gate(task)
        self.tasks.save(task)
        return _freeze_outcome(task)

    def enforce_spec_frozen(self, task_id: str, *, action: str) -> tuple[bool, TaskRecord]:
        task = self.tasks.load(task_id)
        _ensure_spec_fields(task)
        spec_gates = collect_spec_gate_records(
            task,
            action=action,
            created_at=self.clock.now(),
        )
        validation_gates = self.validation.collect_gates(
            task_id,
            task,
            action=action,
            require_existing_report=True,
        )
        task["gates"] = dedupe_gate_records(
            [
                gate
                for gate in task.get("gates", [])
                if gate.get("source") not in {"spec", "spec_validation"}
            ]
            + spec_gates
            + list(validation_gates)
        )
        if spec_gates or validation_gates:
            task["status"] = "blocked"
            task["stage"] = "spec"
            task["workflow_phase"] = "spec_in_review"
            self.tasks.save(task)
            return False, task
        _restore_task_status_after_plan_gate(task)
        self.tasks.save(task)
        return True, task

    def generate_subtasks(self, task_id: str) -> SubtaskGenerationOutcome:
        task = self.tasks.load(task_id)
        _ensure_spec_fields(task)
        task = self.documents.sync_strategy(task_id, task)
        transition = record_planning_lifecycle_transition(
            task,
            LifecycleAction.GENERATE_SUBTASKS,
            gate_sources={"plan", "spec", "lifecycle"},
            created_at=self.clock.now(),
        )
        if not transition.allowed:
            task["status"] = "blocked"
            task["stage"] = (
                "plan_review"
                if any(gate.get("source") == "plan" for gate in task["gates"])
                else "spec"
            )
            task["workflow_phase"] = (
                "plan_in_review" if task["stage"] == "plan_review" else "spec_in_review"
            )
            self.tasks.save(task)
            return _subtask_outcome(task)

        validation_gates = self.validation.collect_gates(
            task_id,
            task,
            action="subtask generation",
            require_existing_report=True,
        )
        if validation_gates:
            task["gates"] = dedupe_gate_records(
                [
                    gate
                    for gate in task.get("gates", [])
                    if gate.get("source") != "spec_validation"
                ]
                + list(validation_gates)
            )
            task["status"] = "blocked"
            task["stage"] = "spec"
            task["workflow_phase"] = "spec_in_review"
            self.tasks.save(task)
            return _subtask_outcome(task)

        task["gates"] = [
            gate for gate in task.get("gates", []) if gate.get("source") != "spec_validation"
        ]
        _restore_task_status_after_plan_gate(task)
        task["subtasks"] = _build_subtasks(task)
        task["workflow_phase"] = "execution"
        self.tasks.save(task)
        return _subtask_outcome(task)


def reopen_task_plan_for_design_replan(
    task: TaskRecord,
    *,
    actor: str,
    notes: str | None,
    clock: ClockPort,
) -> None:
    _ensure_plan_fields(task)
    _ensure_spec_fields(task)
    task["plan_status"] = PLAN_CHANGES_REQUESTED
    task["plan_review_round"] = int(task.get("plan_review_round", 0)) + 1
    task["plan_reviewed_at"] = clock.now()
    task["plan_reviewed_by"] = actor.strip() or "design-audit"
    task["plan_review_notes"] = notes
    task["workflow_phase"] = "plan_revision"
    task["spec_status"] = SPEC_DRAFT
    task["spec_frozen_at"] = None
    task["spec_reviewed_by"] = None
    task["spec_review_notes"] = None
    task["gates"] = dedupe_gate_records(
        [
            gate
            for gate in task.get("gates", [])
            if gate.get("source") not in {"plan", "spec", "spec_validation"}
        ]
        + collect_plan_gate_records(
            task,
            action="execution",
            created_at=clock.now(),
        )
    )
    task["status"] = "blocked"
    task["stage"] = "plan_review"
    _append_review_history(
        task,
        action="design_replan",
        actor=str(task["plan_reviewed_by"]),
        notes=notes,
        timestamp=clock.now(),
    )


def _ensure_plan_fields(task: TaskRecord) -> None:
    task.setdefault("plan_status", PLAN_APPROVED)
    task.setdefault("plan_reviewed_at", None)
    task.setdefault("plan_reviewed_by", None)
    task.setdefault("plan_review_notes", None)
    task.setdefault("plan_review_round", 0)
    task.setdefault("max_plan_review_rounds", 3)
    task.setdefault("plan_review_history", [])
    task.setdefault(
        "workflow_phase",
        "execution" if current_plan_status(task) == PLAN_APPROVED else "plan_in_review",
    )
    ensure_task_design_defaults(task)


def _ensure_spec_fields(task: TaskRecord) -> None:
    task.setdefault("spec_status", SPEC_FROZEN)
    task.setdefault("spec_frozen_at", None)
    task.setdefault("spec_reviewed_by", None)
    task.setdefault("spec_review_notes", None)
    task.setdefault("subtasks", [])
    ensure_task_design_defaults(task)


def _restore_task_status_after_plan_gate(task: TaskRecord) -> None:
    remaining_gates = list(task.get("gates", []))
    if task.get("closed_at"):
        task["status"] = "closed"
        task["stage"] = "done"
        task["workflow_phase"] = "closed"
        return
    if task.get("verify_status") == "passed":
        task["status"] = "verified"
        task["stage"] = "done"
        task["workflow_phase"] = "verified"
        return
    if not remaining_gates:
        task["status"] = "open"
        if task.get("stage") == "plan_review":
            task["stage"] = "spec"
        if current_plan_status(task) == PLAN_APPROVED and current_spec_status(task) == SPEC_FROZEN:
            task["workflow_phase"] = "execution" if task.get("subtasks") else "subtask_planning"
        elif current_plan_status(task) == PLAN_APPROVED:
            task["workflow_phase"] = "spec_drafting"
        else:
            task["workflow_phase"] = "plan_in_review"
        return
    task["status"] = "blocked"


def _append_review_history(
    task: TaskRecord,
    *,
    action: str,
    actor: str,
    notes: str | None,
    timestamp: str,
) -> None:
    history = list(task.get("plan_review_history", []))
    history.append(
        {
            "round": int(task.get("plan_review_round", 0)),
            "action": action,
            "actor": actor,
            "notes": notes,
            "timestamp": timestamp,
        }
    )
    task["plan_review_history"] = history


def _build_subtasks(task: TaskRecord) -> list[dict]:
    strategy = task.get("test_strategy", {})
    categories = [
        ("normal", strategy.get("normal_cases", [])),
        ("edge", strategy.get("edge_cases", [])),
        ("exception", strategy.get("exception_cases", [])),
    ]
    subtasks: list[dict] = []
    counter = 1
    for category, items in categories:
        for item in items:
            name = str(item.get("name", "")).strip()
            if not name:
                continue
            subtasks.append(
                {
                    "id": f"subtask-{counter:03d}",
                    "title": name,
                    "category": category,
                    "status": "queued",
                    "agent_role": "worker",
                    "depends_on": [],
                }
            )
            counter += 1
    if subtasks:
        return subtasks
    return [
        {
            "id": "subtask-001",
            "title": f"Implement {task['slug']}",
            "category": "normal",
            "status": "queued",
            "agent_role": "worker",
            "depends_on": [],
        }
    ]


def _plan_outcome(task: TaskRecord) -> PlanReviewOutcome:
    return PlanReviewOutcome(
        task_id=str(task["id"]),
        plan_status=current_plan_status(task),
        task_status=str(task["status"]),
        gates=list(task["gates"]),
    )


def _freeze_outcome(task: TaskRecord) -> SpecFreezeOutcome:
    return SpecFreezeOutcome(
        task_id=str(task["id"]),
        spec_status=str(task["spec_status"]),
        task_status=str(task["status"]),
        workflow_phase=str(task["workflow_phase"]),
    )


def _subtask_outcome(task: TaskRecord) -> SubtaskGenerationOutcome:
    return SubtaskGenerationOutcome(
        task_id=str(task["id"]),
        workflow_phase=str(task["workflow_phase"]),
        subtasks=list(task.get("subtasks", [])),
    )


__all__ = [
    "PLAN_APPROVED",
    "PLAN_CHANGES_REQUESTED",
    "PLAN_PENDING_REVIEW",
    "PLAN_REVIEW_LIMIT_REACHED",
    "PLAN_STATUSES",
    "SPEC_DRAFT",
    "SPEC_FROZEN",
    "SPEC_STATUSES",
    "PlanningService",
    "current_plan_status",
    "current_spec_status",
    "reopen_task_plan_for_design_replan",
]
