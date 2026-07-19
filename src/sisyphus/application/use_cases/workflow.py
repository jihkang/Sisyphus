from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ...domain.planning.models import PlanStatus, SpecStatus, normalize_plan_status, normalize_spec_status
from ..ports.workflow import (
    CloseoutPort,
    ConformancePort,
    EventPublisherPort,
    FeatureObligationPort,
    ManualInterventionPort,
    ProviderPort,
    ProviderRequest,
    TaskRecord,
    TaskRecordPort,
    VerificationPort,
    WorkflowEvent,
    WorkflowPlanningPort,
)


PLANNER_ROLE = "planner"
WORKER_ROLE = "worker"
REVIEWER_ROLE = "reviewer"
CONFORMANCE_RED = "red"


@dataclass(slots=True)
class WorkflowService:
    tasks: TaskRecordPort
    planning: WorkflowPlanningPort
    obligations: FeatureObligationPort
    conformance: ConformancePort
    provider: ProviderPort
    verification: VerificationPort
    closeout: CloseoutPort
    events: EventPublisherPort
    interventions: ManualInterventionPort

    def advance(self, task_id: str) -> bool:
        task = self.tasks.load(task_id)
        phase = str(task.get("workflow_phase") or "")
        if not bool(task.get("meta", {}).get("auto_loop_enabled", True)):
            return False
        if task.get("status") == "closed":
            return False
        if phase in {"needs_user_input", "promotion_pending", "retarget_required"}:
            return False
        if normalize_plan_status(task.get("plan_status")) != PlanStatus.APPROVED:
            return False

        if normalize_spec_status(task.get("spec_status")) != SpecStatus.FROZEN:
            self.planning.freeze_spec(task_id)
            return True

        if task.get("type") == "feature":
            if self.obligations.converge(task_id):
                return True
            latest_task = self.tasks.load(task_id)
            latest_phase = str(latest_task.get("workflow_phase") or "")
            if latest_task.get("status") == "verified" or latest_phase == "verified":
                return False

        if not task.get("subtasks"):
            self.planning.generate_subtasks(task_id)
            return True

        queued = next(
            (subtask for subtask in task.get("subtasks", []) if subtask.get("status") == "queued"),
            None,
        )
        if queued is not None:
            return self._run_subtask(task, subtask_id=str(queued["id"]))

        if any(subtask.get("status") == "failed" for subtask in task.get("subtasks", [])):
            self._update_phase(task_id, "needs_user_input")
            return True

        subtasks = list(task.get("subtasks", []))
        if subtasks and all(subtask.get("status") == "completed" for subtask in subtasks):
            self._update_phase(task_id, "integration_review")
            verification = self.verification.verify(task_id)
            if verification.gates:
                self._update_phase(task_id, "needs_user_input")
                return True
            closeout = self.closeout.close(task_id, allow_dirty=True)
            if closeout.closed:
                self._update_phase(task_id, "closed")
            else:
                latest_task = self.tasks.load(task_id)
                self._update_phase(
                    task_id,
                    str(latest_task.get("workflow_phase") or "needs_user_input"),
                )
            return True

        return False

    def _run_subtask(self, task: TaskRecord, *, subtask_id: str) -> bool:
        subtask = next(
            item for item in task.get("subtasks", []) if str(item.get("id")) == subtask_id
        )
        pre_check = self.conformance.pre_execution(
            task,
            subtask_id=subtask_id,
            source="workflow.pre_exec",
        )
        self.tasks.save(task)
        self.conformance.write_log(task)
        self.events.publish(
            WorkflowEvent(
                event_type=f"conformance.pre_exec.{pre_check.status}",
                source={"module": "workflow", "checkpoint": "pre_exec"},
                data={
                    "task_id": task["id"],
                    "subtask_id": subtask_id,
                    "summary": pre_check.summary,
                },
            )
        )
        if pre_check.status == CONFORMANCE_RED:
            self._update_subtask_status(str(task["id"]), subtask_id, "failed")
            self._update_phase(str(task["id"]), "needs_user_input")
            return True

        self._update_subtask_status(str(task["id"]), subtask_id, "in_progress")
        self.events.publish(
            WorkflowEvent(
                event_type="subtask.started",
                source={"module": "workflow"},
                data={
                    "task_id": task["id"],
                    "subtask_id": subtask_id,
                    "title": subtask.get("title"),
                },
            )
        )
        exit_code = self.provider.run(
            ProviderRequest(
                provider=str(task.get("meta", {}).get("default_provider") or "codex"),
                task_id=str(task["id"]),
                agent_id=subtask_id,
                role=WORKER_ROLE,
                instruction=(
                    f"Work only on subtask `{subtask.get('title')}` in category "
                    f"`{subtask.get('category')}`. Keep other planned work untouched unless "
                    "required by tests.\n\n"
                    f"{self.conformance.execution_contract(task, subtask)}"
                ),
            )
        )
        latest_task = self.tasks.load(str(task["id"]))
        post_check = self.conformance.post_execution(
            latest_task,
            subtask_id=subtask_id,
            exit_code=exit_code,
            source="workflow.post_exec",
        )
        self.tasks.save(latest_task)
        self.conformance.write_log(latest_task)
        self._update_subtask_status(
            str(task["id"]),
            subtask_id,
            "completed" if exit_code == 0 else "failed",
        )
        self.events.publish(
            WorkflowEvent(
                event_type=f"conformance.post_exec.{post_check.status}",
                source={"module": "workflow", "checkpoint": "post_exec"},
                data={
                    "task_id": task["id"],
                    "subtask_id": subtask_id,
                    "summary": post_check.summary,
                },
            )
        )
        self.events.publish(
            WorkflowEvent(
                event_type="subtask.completed" if exit_code == 0 else "subtask.failed",
                source={"module": "workflow"},
                data={
                    "task_id": task["id"],
                    "subtask_id": subtask_id,
                    "title": subtask.get("title"),
                    "exit_code": exit_code,
                    "conformance_status": post_check.status,
                },
            )
        )
        if exit_code != 0 or post_check.status == CONFORMANCE_RED:
            self._update_phase(str(task["id"]), "needs_user_input")
        return True

    def _update_phase(self, task_id: str, phase: str) -> None:
        def mutate(task: TaskRecord) -> None:
            task["workflow_phase"] = phase
            if phase == "needs_user_input":
                task["status"] = "blocked"

        task = self.tasks.update(task_id, mutate)
        self.events.publish(
            WorkflowEvent(
                event_type="task.updated",
                source={"module": "workflow", "action": "update_phase"},
                data={
                    "task_id": task_id,
                    "workflow_phase": phase,
                    "status": task.get("status"),
                    "conformance_status": self.conformance.status(task),
                },
            )
        )
        if phase == "needs_user_input":
            self.interventions.required(
                task_id=task_id,
                reason="workflow_needs_user_input",
                workflow_phase=phase,
                status=str(task.get("status") or ""),
                detail="workflow paused and requires operator input before continuing",
            )

    def _update_subtask_status(self, task_id: str, subtask_id: str, status: str) -> None:
        def mutate(task: TaskRecord) -> None:
            subtasks: list[dict[str, Any]] = list(task.get("subtasks", []))
            for subtask in subtasks:
                if str(subtask.get("id")) == subtask_id:
                    subtask["status"] = status
                    break
            task["subtasks"] = subtasks

        self.tasks.update(task_id, mutate)


__all__ = [
    "PLANNER_ROLE",
    "REVIEWER_ROLE",
    "WORKER_ROLE",
    "WorkflowService",
]
