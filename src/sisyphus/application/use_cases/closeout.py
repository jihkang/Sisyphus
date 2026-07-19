from __future__ import annotations

from dataclasses import dataclass

from ..closeout_records import evaluate_closeout_lifecycle
from ..planning_records import dedupe_gate_records, make_gate_record
from ..ports.clock import ClockPort
from ..ports.closeout import CloseoutEvidencePort, WorktreeStatusPort
from ..ports.workflow import (
    EventPublisherPort,
    ManualInterventionPort,
    TaskRecordPort,
    WorkflowEvent,
)
from ..results.closeout import CloseOutcome


@dataclass(slots=True)
class CloseoutService:
    tasks: TaskRecordPort
    evidence: CloseoutEvidencePort
    worktree: WorktreeStatusPort
    events: EventPublisherPort
    interventions: ManualInterventionPort
    clock: ClockPort

    def close(self, task_id: str, *, allow_dirty: bool) -> CloseOutcome:
        task = self.tasks.load(task_id)
        gates = [
            gate
            for gate in task.get("gates", [])
            if gate.get("source")
            not in {"close", "plan", "conformance", "promotion", "evidence"}
        ]
        _, lifecycle_gates = evaluate_closeout_lifecycle(
            task,
            created_at=self.clock.now(),
        )
        gates.extend(lifecycle_gates)
        gates.extend(self.evidence.collect_gates(task_id, task))

        dirty = self.worktree.is_dirty(task)
        if dirty and not allow_dirty:
            gates.append(
                make_gate_record(
                    "DIRTY_WORKTREE",
                    "working tree is dirty",
                    "close",
                    created_at=self.clock.now(),
                )
            )
        if dirty and allow_dirty:
            task.setdefault("meta", {})["close_override_used"] = True

        gates = dedupe_gate_records(gates)
        task["gates"] = gates
        if gates:
            return self._record_blocked(task, allow_dirty=allow_dirty, gates=gates)

        task["status"] = "closed"
        task["stage"] = "done"
        task["workflow_phase"] = "closed"
        task["closed_at"] = self.clock.now()
        self.tasks.save(task)
        self._publish_completion(task, closed=True, gate_count=0)
        return CloseOutcome(
            task_id=str(task["id"]),
            status=str(task["status"]),
            closed=True,
            allow_dirty=allow_dirty,
            gates=[],
        )

    def _record_blocked(
        self,
        task: dict,
        *,
        allow_dirty: bool,
        gates: list[dict],
    ) -> CloseOutcome:
        close_gate_codes = {
            gate.get("code") for gate in gates if gate.get("source") == "close"
        }
        if close_gate_codes == {"PROMOTION_REQUIRED"}:
            task["status"] = "verified"
            task["stage"] = "promotion"
            task["workflow_phase"] = "promotion_pending"
        else:
            task["status"] = "blocked"
            task["stage"] = (
                "plan_review" if any(gate.get("source") == "plan" for gate in gates) else "audit"
            )
        self.tasks.save(task)
        self._publish_completion(task, closed=False, gate_count=len(gates))
        if close_gate_codes == {"PROMOTION_REQUIRED"}:
            self.interventions.required(
                task_id=str(task["id"]),
                reason="promotion_required",
                workflow_phase="promotion_pending",
                status=str(task.get("status") or ""),
                detail="task passed verify but cannot close until promotion is recorded",
            )
        return CloseOutcome(
            task_id=str(task["id"]),
            status=str(task["status"]),
            closed=False,
            allow_dirty=allow_dirty,
            gates=gates,
        )

    def _publish_completion(self, task: dict, *, closed: bool, gate_count: int) -> None:
        self.events.publish(
            WorkflowEvent(
                event_type="close.completed",
                source={"module": "closeout"},
                data={
                    "task_id": task["id"],
                    "closed": closed,
                    "status": task["status"],
                    "gate_count": gate_count,
                },
            )
        )


__all__ = ["CloseoutService"]
