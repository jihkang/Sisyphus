from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .metrics import publish_manual_intervention_required
from .config import SisyphusConfig
from .conformance import mark_design_anchor
from .design import ensure_task_design_defaults, freeze_design_anchor
from .state import load_task_record, save_task_record, utc_now
from .strategy import sync_test_strategy_from_docs


PLAN_PENDING_REVIEW = "pending_review"
PLAN_APPROVED = "approved"
PLAN_CHANGES_REQUESTED = "changes_requested"
PLAN_REVIEW_LIMIT_REACHED = "PLAN_REVIEW_LIMIT_REACHED"
PLAN_STATUSES = {
    PLAN_PENDING_REVIEW,
    PLAN_APPROVED,
    PLAN_CHANGES_REQUESTED,
}
SPEC_DRAFT = "draft"
SPEC_FROZEN = "frozen"
SPEC_STATUSES = {
    SPEC_DRAFT,
    SPEC_FROZEN,
}


@dataclass(slots=True)
class PlanReviewOutcome:
    task_id: str
    plan_status: str
    task_status: str
    gates: list[dict]


@dataclass(slots=True)
class SpecFreezeOutcome:
    task_id: str
    spec_status: str
    task_status: str
    workflow_phase: str


@dataclass(slots=True)
class SubtaskGenerationOutcome:
    task_id: str
    workflow_phase: str
    subtasks: list[dict]


def current_plan_status(task: dict) -> str:
    status = str(task.get("plan_status") or PLAN_APPROVED)
    if status not in PLAN_STATUSES:
        return PLAN_APPROVED
    return status


def current_spec_status(task: dict) -> str:
    status = str(task.get("spec_status") or SPEC_FROZEN)
    if status not in SPEC_STATUSES:
        return SPEC_FROZEN
    return status


def collect_plan_gates(task: dict, *, action: str) -> list[dict]:
    status = current_plan_status(task)
    if int(task.get("plan_review_round", 0)) >= int(task.get("max_plan_review_rounds", 3)) and status != PLAN_APPROVED:
        return [_gate(PLAN_REVIEW_LIMIT_REACHED, f"task plan review exceeded maximum rounds before {action}", source="plan")]
    if status == PLAN_APPROVED:
        return []
    if status == PLAN_CHANGES_REQUESTED:
        return [_gate("PLAN_CHANGES_REQUESTED", f"task plan has requested changes before {action}", source="plan")]
    return [_gate("PLAN_APPROVAL_REQUIRED", f"task plan must be approved before {action}", source="plan")]


def collect_spec_execution_gates(task: dict, *, action: str) -> list[dict]:
    if current_spec_status(task) == SPEC_FROZEN:
        return []
    return [_gate("SPEC_FREEZE_REQUIRED", f"task spec must be frozen before {action}", source="spec")]


def approve_task_plan(
    repo_root: Path,
    config: SisyphusConfig,
    task_id: str,
    *,
    reviewer: str,
    notes: str | None,
) -> PlanReviewOutcome:
    task, task_file = load_task_record(repo_root=repo_root, task_dir_name=config.task_dir, task_id=task_id)
    _ensure_plan_fields(task)
    task["plan_status"] = PLAN_APPROVED
    task["plan_reviewed_at"] = utc_now()
    task["plan_reviewed_by"] = reviewer.strip() or "operator"
    task["plan_review_notes"] = notes
    task["workflow_phase"] = "spec_drafting"
    task["gates"] = [gate for gate in task.get("gates", []) if gate.get("source") != "plan"]
    _append_review_history(task, action="approve", actor=task["plan_reviewed_by"], notes=notes)
    _restore_task_status_after_plan_gate(task)
    save_task_record(task_file=task_file, task=task)
    publish_manual_intervention_required(
        repo_root,
        config,
        task_id=str(task["id"]),
        reason="spec_freeze_required",
        workflow_phase="spec_drafting",
        status=str(task.get("status") or ""),
        detail="plan approval completed and the task now awaits spec freeze",
    )
    return PlanReviewOutcome(
        task_id=task["id"],
        plan_status=task["plan_status"],
        task_status=task["status"],
        gates=task["gates"],
    )


def request_plan_changes(
    repo_root: Path,
    config: SisyphusConfig,
    task_id: str,
    *,
    reviewer: str,
    notes: str | None,
) -> PlanReviewOutcome:
    task, task_file = load_task_record(repo_root=repo_root, task_dir_name=config.task_dir, task_id=task_id)
    _ensure_plan_fields(task)
    task["plan_status"] = PLAN_CHANGES_REQUESTED
    task["plan_review_round"] = int(task.get("plan_review_round", 0)) + 1
    task["plan_reviewed_at"] = utc_now()
    task["plan_reviewed_by"] = reviewer.strip() or "operator"
    task["plan_review_notes"] = notes
    task["workflow_phase"] = "needs_user_input" if int(task["plan_review_round"]) >= int(task.get("max_plan_review_rounds", 3)) else "plan_revision"
    task["gates"] = _dedupe_gates(
        [gate for gate in task.get("gates", []) if gate.get("source") != "plan"] +
        collect_plan_gates(task, action="execution")
    )
    _append_review_history(task, action="request_changes", actor=task["plan_reviewed_by"], notes=notes)
    task["status"] = "blocked"
    task["stage"] = "plan_review"
    save_task_record(task_file=task_file, task=task)
    publish_manual_intervention_required(
        repo_root,
        config,
        task_id=str(task["id"]),
        reason="plan_changes_requested",
        workflow_phase=str(task.get("workflow_phase") or ""),
        status=str(task.get("status") or ""),
        detail="plan review requested changes before execution can continue",
    )
    return PlanReviewOutcome(
        task_id=task["id"],
        plan_status=task["plan_status"],
        task_status=task["status"],
        gates=task["gates"],
    )


def revise_task_plan(
    repo_root: Path,
    config: SisyphusConfig,
    task_id: str,
    *,
    author: str,
    notes: str | None,
) -> PlanReviewOutcome:
    task, task_file = load_task_record(repo_root=repo_root, task_dir_name=config.task_dir, task_id=task_id)
    _ensure_plan_fields(task)
    task["plan_status"] = PLAN_PENDING_REVIEW
    task["plan_reviewed_at"] = utc_now()
    task["plan_reviewed_by"] = author.strip() or "operator"
    task["plan_review_notes"] = notes
    task["workflow_phase"] = "plan_in_review"
    task["gates"] = [gate for gate in task.get("gates", []) if gate.get("source") != "plan"]
    _append_review_history(task, action="revise", actor=task["plan_reviewed_by"], notes=notes)
    _restore_task_status_after_plan_gate(task)
    task["stage"] = "plan_review"
    save_task_record(task_file=task_file, task=task)
    publish_manual_intervention_required(
        repo_root,
        config,
        task_id=str(task["id"]),
        reason="plan_review_required",
        workflow_phase="plan_in_review",
        status=str(task.get("status") or ""),
        detail="a revised plan now awaits another review decision",
    )
    return PlanReviewOutcome(
        task_id=task["id"],
        plan_status=task["plan_status"],
        task_status=task["status"],
        gates=task["gates"],
    )


def enforce_plan_approved(
    repo_root: Path,
    config: SisyphusConfig,
    task_id: str,
    *,
    action: str,
) -> tuple[bool, dict]:
    task, task_file = load_task_record(repo_root=repo_root, task_dir_name=config.task_dir, task_id=task_id)
    _ensure_plan_fields(task)
    plan_gates = collect_plan_gates(task, action=action)
    task["gates"] = _dedupe_gates(
        [gate for gate in task.get("gates", []) if gate.get("source") != "plan"] + plan_gates
    )
    if plan_gates:
        task["status"] = "blocked"
        task["stage"] = "plan_review"
        save_task_record(task_file=task_file, task=task)
        return False, task
    _restore_task_status_after_plan_gate(task)
    save_task_record(task_file=task_file, task=task)
    return True, task


def freeze_task_spec(
    repo_root: Path,
    config: SisyphusConfig,
    task_id: str,
    *,
    reviewer: str,
    notes: str | None,
) -> SpecFreezeOutcome:
    task, task_file = load_task_record(repo_root=repo_root, task_dir_name=config.task_dir, task_id=task_id)
    _ensure_plan_fields(task)
    _ensure_spec_fields(task)
    task = sync_test_strategy_from_docs(task=task, task_dir=task_file.parent)
    task["plan_status"] = current_plan_status(task)
    task["gates"] = [gate for gate in task.get("gates", []) if gate.get("source") != "spec"]
    plan_gates = collect_plan_gates(task, action="spec freeze")
    if plan_gates:
        task["gates"] = _dedupe_gates([gate for gate in task.get("gates", []) if gate.get("source") != "plan"] + plan_gates)
        task["status"] = "blocked"
        task["stage"] = "plan_review"
        task["workflow_phase"] = "needs_user_input"
        save_task_record(task_file=task_file, task=task)
        return SpecFreezeOutcome(
            task_id=task["id"],
            spec_status=task["spec_status"],
            task_status=task["status"],
            workflow_phase=task["workflow_phase"],
        )
    task["spec_status"] = SPEC_FROZEN
    task["spec_frozen_at"] = utc_now()
    task["spec_reviewed_by"] = reviewer.strip() or "operator"
    task["spec_review_notes"] = notes
    freeze_design_anchor(task, frozen_at=task["spec_frozen_at"])
    mark_design_anchor(task, source="planning.freeze_task_spec")
    task["workflow_phase"] = "subtask_planning"
    _restore_task_status_after_plan_gate(task)
    save_task_record(task_file=task_file, task=task)
    return SpecFreezeOutcome(
        task_id=task["id"],
        spec_status=task["spec_status"],
        task_status=task["status"],
        workflow_phase=task["workflow_phase"],
    )


def enforce_spec_frozen(
    repo_root: Path,
    config: SisyphusConfig,
    task_id: str,
    *,
    action: str,
) -> tuple[bool, dict]:
    task, task_file = load_task_record(repo_root=repo_root, task_dir_name=config.task_dir, task_id=task_id)
    _ensure_spec_fields(task)
    spec_gates = collect_spec_execution_gates(task, action=action)
    task["gates"] = _dedupe_gates(
        [gate for gate in task.get("gates", []) if gate.get("source") != "spec"] + spec_gates
    )
    if spec_gates:
        task["status"] = "blocked"
        task["stage"] = "spec"
        task["workflow_phase"] = "spec_in_review"
        save_task_record(task_file=task_file, task=task)
        return False, task
    save_task_record(task_file=task_file, task=task)
    return True, task


def generate_subtasks(
    repo_root: Path,
    config: SisyphusConfig,
    task_id: str,
) -> SubtaskGenerationOutcome:
    task, task_file = load_task_record(repo_root=repo_root, task_dir_name=config.task_dir, task_id=task_id)
    _ensure_spec_fields(task)
    task_dir = task_file.parent
    task = sync_test_strategy_from_docs(task=task, task_dir=task_dir)
    task["subtasks"] = _build_subtasks(task)
    task["workflow_phase"] = "execution"
    save_task_record(task_file=task_file, task=task)
    return SubtaskGenerationOutcome(
        task_id=task["id"],
        workflow_phase=task["workflow_phase"],
        subtasks=task["subtasks"],
    )


def _ensure_plan_fields(task: dict) -> None:
    task.setdefault("plan_status", PLAN_APPROVED)
    task.setdefault("plan_reviewed_at", None)
    task.setdefault("plan_reviewed_by", None)
    task.setdefault("plan_review_notes", None)
    task.setdefault("plan_review_round", 0)
    task.setdefault("max_plan_review_rounds", 3)
    task.setdefault("plan_review_history", [])
    task.setdefault("workflow_phase", "execution" if current_plan_status(task) == PLAN_APPROVED else "plan_in_review")
    ensure_task_design_defaults(task)


def _ensure_spec_fields(task: dict) -> None:
    task.setdefault("spec_status", SPEC_FROZEN)
    task.setdefault("spec_frozen_at", None)
    task.setdefault("spec_reviewed_by", None)
    task.setdefault("spec_review_notes", None)
    task.setdefault("subtasks", [])
    ensure_task_design_defaults(task)


def _restore_task_status_after_plan_gate(task: dict) -> None:
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


def _append_review_history(task: dict, *, action: str, actor: str, notes: str | None) -> None:
    history = list(task.get("plan_review_history", []))
    history.append(
        {
            "round": int(task.get("plan_review_round", 0)),
            "action": action,
            "actor": actor,
            "notes": notes,
            "timestamp": utc_now(),
        }
    )
    task["plan_review_history"] = history


def reopen_task_plan_for_design_replan(
    task: dict,
    *,
    actor: str,
    notes: str | None,
) -> None:
    _ensure_plan_fields(task)
    _ensure_spec_fields(task)
    task["plan_status"] = PLAN_CHANGES_REQUESTED
    task["plan_review_round"] = int(task.get("plan_review_round", 0)) + 1
    task["plan_reviewed_at"] = utc_now()
    task["plan_reviewed_by"] = actor.strip() or "design-audit"
    task["plan_review_notes"] = notes
    task["workflow_phase"] = "plan_revision"
    task["spec_status"] = SPEC_DRAFT
    task["spec_frozen_at"] = None
    task["spec_reviewed_by"] = None
    task["spec_review_notes"] = None
    task["gates"] = _dedupe_gates(
        [gate for gate in task.get("gates", []) if gate.get("source") not in {"plan", "spec"}] +
        collect_plan_gates(task, action="execution")
    )
    task["status"] = "blocked"
    task["stage"] = "plan_review"
    _append_review_history(task, action="design_replan", actor=task["plan_reviewed_by"], notes=notes)


def _build_subtasks(task: dict) -> list[dict]:
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


def _gate(code: str, message: str, source: str) -> dict:
    return {
        "code": code,
        "message": message,
        "blocking": True,
        "source": source,
        "created_at": utc_now(),
    }


def _dedupe_gates(gates: list[dict]) -> list[dict]:
    seen: set[tuple[str, str]] = set()
    deduped: list[dict] = []
    for gate in gates:
        key = (gate.get("code", ""), gate.get("message", ""))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(gate)
    return deduped
