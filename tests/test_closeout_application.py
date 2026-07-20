from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest import mock

from sisyphus.application.ports.closeout import WorktreeStatusError
from sisyphus.application.ports.review import ExternalReviewEvidence
from sisyphus.application.use_cases.closeout import CloseoutService
from sisyphus.infra.closeout.git_status import (
    GitWorktreeStatusAdapter,
    is_dirty_worktree,
)


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
    def __init__(
        self,
        calls: list[str],
        *,
        dirty: bool = False,
        error: WorktreeStatusError | None = None,
    ) -> None:
        self.calls = calls
        self.dirty = dirty
        self.error = error

    def is_dirty(self, task: dict) -> bool:
        self.calls.append("worktree.is_dirty")
        if self.error is not None:
            raise self.error
        return self.dirty


class ExternalReviewsFake:
    def __init__(
        self,
        *,
        current_head_sha: str = "a" * 40,
        dirty_paths: tuple[str, ...] = (),
    ) -> None:
        self.current_head_sha = current_head_sha
        self.dirty_paths = dirty_paths
        self.inspect_calls = 0

    def scope(self, workspace: str, task: dict):
        raise AssertionError("closeout must inspect the recorded envelope")

    def inspect(self, workspace: str, envelope_path: str, task: dict):
        self.inspect_calls += 1
        review = task["test_strategy"]["external_llm"]
        return ExternalReviewEvidence(
            envelope_path=envelope_path,
            envelope_digest=review["envelope_digest"],
            envelope_size_bytes=256,
            provider=review["provider"],
            reviewer=review["reviewer"],
            reviewed_head_sha=review["reviewed_head_sha"],
            scope_digest=review["scope_digest"],
            report_path=review["report_path"],
            report_digest=review["report_digest"],
            report_size_bytes=128,
            summary="No blocking findings.",
            findings=(),
            current_head_sha=self.current_head_sha,
            current_scope_digest=review["scope_digest"],
            document_digests=(),
            dirty_paths=self.dirty_paths,
        )


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

    def test_worktree_inspection_failure_cannot_be_bypassed_by_dirty_override(self) -> None:
        service, dependencies, _ = _service(
            _task(),
            worktree_error=WorktreeStatusError("git status unavailable"),
        )

        outcome = service.close("TF-1", allow_dirty=True)

        self.assertFalse(outcome.closed)
        self.assertIn("WORKTREE_STATUS_UNAVAILABLE", {gate["code"] for gate in outcome.gates})
        self.assertFalse(dependencies["tasks"].task["meta"]["close_override_used"])

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

    def test_close_rejects_verify_status_not_bound_to_current_external_review(self) -> None:
        task = _reviewed_task()
        task["test_strategy"]["external_llm"]["report_digest"] = "sha256:" + "c" * 64
        service, _dependencies, _calls = _service(task)

        outcome = service.close("TF-1", allow_dirty=False)

        self.assertFalse(outcome.closed)
        self.assertIn("EXTERNAL_LLM_REVIEW_STALE", {gate["code"] for gate in outcome.gates})

    def test_close_reinspects_review_head_even_for_clean_commit(self) -> None:
        task = _reviewed_task()
        service, _dependencies, _calls = _service(
            task,
            external_review=ExternalReviewsFake(current_head_sha="c" * 40),
        )

        outcome = service.close("TF-1", allow_dirty=True)

        self.assertFalse(outcome.closed)
        self.assertIn("EXTERNAL_LLM_REVIEW_STALE", {gate["code"] for gate in outcome.gates})

    def test_allow_dirty_does_not_bypass_unreviewed_code_change(self) -> None:
        task = _reviewed_task()
        service, _dependencies, _calls = _service(
            task,
            dirty=True,
            external_review=ExternalReviewsFake(
                dirty_paths=("src/sisyphus/runtime.py",),
            ),
        )

        outcome = service.close("TF-1", allow_dirty=True)

        self.assertFalse(outcome.closed)
        self.assertIn("EXTERNAL_LLM_REVIEW_STALE", {gate["code"] for gate in outcome.gates})

    def test_legacy_constructor_remains_valid_for_task_without_review(self) -> None:
        _service_with_adapter, dependencies, _calls = _service(_task())
        legacy_dependencies = {
            key: value
            for key, value in dependencies.items()
            if key != "external_reviews"
        }

        outcome = CloseoutService(**legacy_dependencies).close("TF-1", allow_dirty=False)

        self.assertTrue(outcome.closed)

    def test_review_required_task_fails_closed_without_evidence_adapter(self) -> None:
        _service_with_adapter, dependencies, _calls = _service(_reviewed_task())
        legacy_dependencies = {
            key: value
            for key, value in dependencies.items()
            if key != "external_reviews"
        }

        outcome = CloseoutService(**legacy_dependencies).close("TF-1", allow_dirty=True)

        self.assertFalse(outcome.closed)
        self.assertIn("EXTERNAL_LLM_REVIEW_STALE", {gate["code"] for gate in outcome.gates})

    def test_event_failure_occurs_after_retryable_state_is_saved(self) -> None:
        service, dependencies, _ = _service(_task(), event_failure=True)

        with self.assertRaisesRegex(RuntimeError, "event sink unavailable"):
            service.close("TF-1", allow_dirty=False)

        self.assertEqual(dependencies["tasks"].save_count, 1)
        self.assertEqual(dependencies["tasks"].task["status"], "closed")

    def test_git_status_adapter_raises_when_git_cannot_run(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            with mock.patch(
                "sisyphus.infra.closeout.git_status.subprocess.run",
                side_effect=FileNotFoundError("git"),
            ):
                with self.assertRaisesRegex(WorktreeStatusError, "failed to inspect"):
                    is_dirty_worktree(Path(temp_dir))

    def test_git_status_adapter_raises_for_invalid_repository(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            completed = subprocess.CompletedProcess(
                args=["git", "status"],
                returncode=128,
                stdout="",
                stderr="fatal: not a git repository",
            )
            with mock.patch(
                "sisyphus.infra.closeout.git_status.subprocess.run",
                return_value=completed,
            ):
                with self.assertRaisesRegex(WorktreeStatusError, "not a git repository"):
                    is_dirty_worktree(Path(temp_dir))

    def test_git_status_adapter_rejects_when_no_candidate_directory_exists(self) -> None:
        missing = Path(tempfile.gettempdir()) / "sisyphus-missing-closeout-worktree"
        adapter = GitWorktreeStatusAdapter(missing)

        with self.assertRaisesRegex(WorktreeStatusError, "no working tree path"):
            adapter.is_dirty({"worktree_path": str(missing)})


def _service(
    task: dict,
    *,
    dirty: bool = False,
    worktree_error: WorktreeStatusError | None = None,
    evidence_gates: tuple[dict, ...] = (),
    event_failure: bool = False,
    external_review: ExternalReviewsFake | None = None,
) -> tuple[CloseoutService, dict[str, object], list[str]]:
    calls: list[str] = []
    dependencies = {
        "tasks": MemoryTasks(task, calls),
        "evidence": EvidenceFake(calls, evidence_gates),
        "worktree": WorktreeFake(calls, dirty=dirty, error=worktree_error),
        "events": EventsFake(calls, fail=event_failure),
        "interventions": InterventionsFake(calls),
        "clock": FixedClock(),
        "external_reviews": external_review or ExternalReviewsFake(),
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


def _review_with_binding() -> dict:
    values = {
        "envelope_digest": "sha256:" + "e" * 64,
        "report_digest": "sha256:" + "b" * 64,
        "reviewed_head_sha": "a" * 40,
        "scope_digest": "sha256:" + "s" * 64,
    }
    return {
        "required": True,
        "status": "passed",
        "provider": "independent Codex reviewer",
        "reviewer": "independent-codex-agent",
        "envelope_path": ".planning/tasks/TF-1/artifacts/reviews/review.json",
        "report_path": ".planning/tasks/TF-1/artifacts/reviews/review.md",
        "finding_count": 0,
        "blocking_finding_count": 0,
        "verification_output_paths": [
            "VERIFY.md",
            "artifacts/evidence/evidence-graph.json",
        ],
        "promotion_output_paths": [],
        **values,
        "verification_binding": {
            **values,
            "verified_at": "2026-07-19T12:00:00Z",
        },
    }


def _reviewed_task() -> dict:
    task = _task()
    task.update(
        {
            "worktree_path": "/workspace",
            "task_dir": ".planning/tasks/TF-1",
            "docs": {"verify": "VERIFY.md"},
            "test_strategy": {"external_llm": _review_with_binding()},
        }
    )
    return task


if __name__ == "__main__":
    unittest.main()
