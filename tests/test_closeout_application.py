from __future__ import annotations

from copy import deepcopy
import unittest

from sisyphus.application.use_cases.closeout import CloseoutService


class MemoryTasks:
    def __init__(self, task: dict, calls: list[str]) -> None:
        self.task = deepcopy(task)
        self.calls = calls
        self.save_count = 0

    def load(self, task_id: str) -> dict:
        self.calls.append("task.load")
        if task_id != self.task["id"]:
            raise KeyError(task_id)
        return self.task

    def save(self, task: dict) -> None:
        self.calls.append("task.save")
        self.task = task
        self.save_count += 1

    def update(self, task_id: str, mutator) -> dict:
        replacement = mutator(self.task)
        if replacement is not None:
            self.task = replacement
        return self.task


class EvidenceFake:
    def __init__(self, calls: list[str], gates: tuple[dict, ...] = ()) -> None:
        self.calls = calls
        self.gates = gates

    def collect_gates(self, task_id: str, task: dict) -> tuple[dict, ...]:
        self.calls.append("evidence.collect")
        return self.gates


class WorktreeFake:
    def __init__(self, calls: list[str], *, dirty: bool = False) -> None:
        self.calls = calls
        self.dirty = dirty

    def is_dirty(self, task: dict) -> bool:
        self.calls.append("worktree.is_dirty")
        return self.dirty


class EventsFake:
    def __init__(self, calls: list[str], *, fail: bool = False) -> None:
        self.calls = calls
        self.fail = fail
        self.events = []

    def publish(self, event) -> None:
        self.calls.append("event.publish")
        self.events.append(event)
        if self.fail:
            raise RuntimeError("event sink unavailable")


class InterventionsFake:
    def __init__(self, calls: list[str]) -> None:
        self.calls = calls
        self.requests: list[dict[str, str]] = []

    def required(self, **request: str) -> None:
        self.calls.append("intervention.required")
        self.requests.append(request)


class FixedClock:
    def now(self) -> str:
        return "2026-07-19T12:00:00Z"


class CloseoutApplicationTests(unittest.TestCase):
    def test_success_persists_before_publishing_completion(self) -> None:
        service, dependencies, calls = _service(_task())

        outcome = service.close("TF-1", allow_dirty=False)

        self.assertTrue(outcome.closed)
        self.assertEqual(outcome.gates, [])
        self.assertEqual(dependencies["tasks"].task["closed_at"], "2026-07-19T12:00:00Z")
        self.assertEqual(
            calls,
            [
                "task.load",
                "evidence.collect",
                "worktree.is_dirty",
                "task.save",
                "event.publish",
            ],
        )
        event = dependencies["events"].events[0]
        self.assertEqual(event.event_type, "close.completed")
        self.assertEqual(event.data["gate_count"], 0)

    def test_dirty_retry_removes_previous_close_gate_and_records_override(self) -> None:
        service, dependencies, _ = _service(_task(), dirty=True)

        blocked = service.close("TF-1", allow_dirty=False)
        closed = service.close("TF-1", allow_dirty=True)

        self.assertFalse(blocked.closed)
        self.assertEqual([gate["code"] for gate in blocked.gates], ["DIRTY_WORKTREE"])
        self.assertTrue(closed.closed)
        self.assertEqual(closed.gates, [])
        self.assertTrue(dependencies["tasks"].task["meta"]["close_override_used"])

    def test_promotion_only_gate_preserves_verified_state_and_requests_operator(self) -> None:
        task = _task()
        task["promotion"] = {"required": True, "status": "promotion_pending"}
        service, dependencies, calls = _service(task)

        outcome = service.close("TF-1", allow_dirty=False)

        self.assertFalse(outcome.closed)
        self.assertEqual(dependencies["tasks"].task["status"], "verified")
        self.assertEqual(dependencies["tasks"].task["workflow_phase"], "promotion_pending")
        self.assertEqual(
            dependencies["interventions"].requests[0]["reason"],
            "promotion_required",
        )
        self.assertLess(calls.index("event.publish"), calls.index("intervention.required"))

    def test_evidence_gate_blocks_in_audit_stage(self) -> None:
        gate = {
            "code": "EVIDENCE_GRAPH_MISSING",
            "message": "missing",
            "blocking": True,
            "source": "evidence",
            "created_at": "2026-07-19T12:00:00Z",
        }
        service, dependencies, _ = _service(_task(), evidence_gates=(gate,))

        outcome = service.close("TF-1", allow_dirty=False)

        self.assertFalse(outcome.closed)
        self.assertEqual(outcome.gates, [gate])
        self.assertEqual(dependencies["tasks"].task["stage"], "audit")
        self.assertEqual(dependencies["interventions"].requests, [])

    def test_event_failure_occurs_after_retryable_state_is_saved(self) -> None:
        service, dependencies, _ = _service(_task(), event_failure=True)

        with self.assertRaisesRegex(RuntimeError, "event sink unavailable"):
            service.close("TF-1", allow_dirty=False)

        self.assertEqual(dependencies["tasks"].save_count, 1)
        self.assertEqual(dependencies["tasks"].task["status"], "closed")


def _service(
    task: dict,
    *,
    dirty: bool = False,
    evidence_gates: tuple[dict, ...] = (),
    event_failure: bool = False,
) -> tuple[CloseoutService, dict[str, object], list[str]]:
    calls: list[str] = []
    dependencies = {
        "tasks": MemoryTasks(task, calls),
        "evidence": EvidenceFake(calls, evidence_gates),
        "worktree": WorktreeFake(calls, dirty=dirty),
        "events": EventsFake(calls, fail=event_failure),
        "interventions": InterventionsFake(calls),
        "clock": FixedClock(),
    }
    return CloseoutService(**dependencies), dependencies, calls


def _task() -> dict:
    return {
        "id": "TF-1",
        "type": "issue",
        "status": "verified",
        "stage": "done",
        "workflow_phase": "verified",
        "plan_status": "approved",
        "spec_status": "frozen",
        "verify_status": "passed",
        "closed_at": None,
        "promotion": {"required": False, "status": "not_required"},
        "gates": [],
        "subtasks": [],
        "meta": {"close_override_used": False},
    }


if __name__ == "__main__":
    unittest.main()
