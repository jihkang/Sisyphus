from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import sys
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))


from sisyphus.application.results.artifacts import ArtifactRef  # noqa: E402
from sisyphus.application.ports.review import (  # noqa: E402
    ExternalReviewEvidence,
    ExternalReviewScopeEvidence,
)
from sisyphus.application.use_cases.verification import VerificationService  # noqa: E402
from sisyphus.domain.lifecycle import ConformanceState  # noqa: E402
from sisyphus.domain.verification import CommandExecution, VerificationStatus  # noqa: E402


class MemoryTasks:
    def __init__(self, task: dict) -> None:
        self.task = deepcopy(task)
        self.save_count = 0

    def load(self, task_id: str) -> dict:
        if task_id != self.task["id"]:
            raise KeyError(task_id)
        return self.task

    def save(self, task: dict) -> None:
        self.task = task
        self.save_count += 1

    def update(self, task_id: str, mutator) -> dict:
        replacement = mutator(self.task)
        if replacement is not None:
            self.task = replacement
        return self.task


class PlanningDocumentsFake:
    def sync_strategy(self, task_id: str, task: dict) -> dict:
        return task


class DocumentsFake:
    def __init__(self) -> None:
        self.contents = {
            "BRIEF.md": "# Brief\n\n- [x] Explicit criterion\n",
            "PLAN.md": "# Plan\n\nComplete\n",
        }
        self.writes: list[tuple[str, str]] = []

    def read(self, task_id: str, relative_path: str) -> str | None:
        return self.contents.get(relative_path)

    def write(self, task_id: str, relative_path: str, content: str) -> ArtifactRef:
        self.writes.append((relative_path, content))
        self.contents[relative_path] = content
        return ArtifactRef(relative_path=relative_path)


class ValidationFake:
    def __init__(self, gates: tuple[dict, ...] = ()) -> None:
        self.gates = gates

    def required(self, task_id: str, task: dict) -> bool:
        return True

    def collect_gates(self, task_id: str, task: dict, **kwargs) -> tuple[dict, ...]:
        return self.gates


class ConformanceFake:
    def __init__(self) -> None:
        self.appended: list[dict[str, object]] = []

    def snapshot(self, task: dict) -> ConformanceState:
        return ConformanceState()

    def append(self, task: dict, **entry) -> dict:
        self.appended.append(entry)
        return task


class CommandsFake:
    def __init__(self, status: VerificationStatus = VerificationStatus.PASSED) -> None:
        self.status = status
        self.calls: list[tuple[str, tuple[str, ...]]] = []
        self.on_run = None

    def run(self, task_id: str, commands: tuple[str, ...]) -> tuple[CommandExecution, ...]:
        self.calls.append((task_id, commands))
        if self.on_run is not None:
            self.on_run()
        if not commands:
            return ()
        exit_code = 0 if self.status == VerificationStatus.PASSED else 1
        return (
            CommandExecution(
                name=commands[0],
                command=commands[0],
                status=self.status,
                exit_code=exit_code,
                started_at="2026-07-19T12:00:00Z",
                finished_at="2026-07-19T12:00:00Z",
                duration_ms=None,
                output_excerpt="ok" if exit_code == 0 else "failed",
            ),
        )


class EvidenceFake:
    def __init__(self) -> None:
        self.calls: list[tuple[str, int]] = []

    def write(self, task_id: str, task: dict, command_results: tuple[CommandExecution, ...]) -> None:
        self.calls.append((task_id, len(command_results)))


class ExternalReviewsFake:
    def __init__(self, evidence: ExternalReviewEvidence | None = None) -> None:
        self.evidence = evidence
        self.evidence_after: ExternalReviewEvidence | None = None
        self.evidence_after_call = 2
        self.calls: list[tuple[str, str]] = []

    def scope(self, workspace: str, task: dict) -> ExternalReviewScopeEvidence:
        if self.evidence is None:
            raise AssertionError("external review evidence was not expected")
        return ExternalReviewScopeEvidence(
            current_head_sha=self.evidence.current_head_sha,
            scope_digest=self.evidence.current_scope_digest,
            document_digests=self.evidence.document_digests,
        )

    def inspect(
        self,
        workspace: str,
        envelope_path: str,
        task: dict,
    ) -> ExternalReviewEvidence:
        self.calls.append((workspace, envelope_path))
        if self.evidence is None:
            raise AssertionError("external review evidence was not expected")
        if len(self.calls) >= self.evidence_after_call and self.evidence_after is not None:
            return self.evidence_after
        return self.evidence


class EventsFake:
    def __init__(self) -> None:
        self.events = []

    def publish(self, event) -> None:
        self.events.append(event)


class FixedClock:
    def now(self) -> str:
        return "2026-07-19T12:00:00Z"


class VerificationApplicationTests(unittest.TestCase):
    def test_lifecycle_gate_blocks_before_commands_and_evidence(self) -> None:
        service, dependencies = _service(_task(plan_status="pending_review"))

        outcome = service.verify("TF-1")

        self.assertEqual(outcome.status, "failed")
        self.assertEqual(outcome.stage, "plan_review")
        self.assertEqual(outcome.audit_attempts, 0)
        self.assertEqual(dependencies["commands"].calls, [])
        self.assertEqual(dependencies["evidence"].calls, [])
        self.assertEqual(dependencies["documents"].writes[0][0], "VERIFY.md")

    def test_successful_command_produces_typed_receipt_and_verified_state(self) -> None:
        service, dependencies = _service(_task())

        outcome = service.verify("TF-1")

        self.assertEqual(outcome.status, "passed")
        self.assertEqual(outcome.stage, "done")
        self.assertEqual(outcome.verify_artifact, ArtifactRef("VERIFY.md"))
        self.assertEqual(outcome.command_results[0].status, VerificationStatus.PASSED)
        task = dependencies["tasks"].task
        self.assertEqual(task["workflow_phase"], "verified")
        self.assertEqual(task["last_verify_results"][0]["exit_code"], 0)
        self.assertEqual(dependencies["evidence"].calls, [("TF-1", 1)])
        self.assertEqual(dependencies["events"].events[0].event_type, "verify.completed")

    def test_failed_command_adds_verify_gate(self) -> None:
        service, dependencies = _service(
            _task(),
            command_status=VerificationStatus.FAILED,
        )

        outcome = service.verify("TF-1")

        self.assertEqual(outcome.status, "failed")
        self.assertIn("VERIFY_FAILED", {gate["code"] for gate in outcome.gates})
        self.assertEqual(dependencies["tasks"].task["status"], "blocked")

    def test_spec_validation_gate_skips_command_execution(self) -> None:
        gate = {
            "code": "SPEC_VALIDATION_STALE",
            "message": "stale",
            "blocking": True,
            "source": "spec_validation",
            "created_at": "2026-07-19T12:00:00Z",
        }
        service, dependencies = _service(_task(), validation_gates=(gate,))

        outcome = service.verify("TF-1")

        self.assertEqual(outcome.stage, "spec")
        self.assertEqual(dependencies["commands"].calls, [])
        self.assertEqual(dependencies["tasks"].task["workflow_phase"], "spec_in_review")

    def test_underdesigned_task_reopens_plan(self) -> None:
        task = _task()
        task["design"] = {
            "mode": "none",
            "layer_impact": "layer-adding",
        }
        service, dependencies = _service(task)

        outcome = service.verify("TF-1")

        self.assertEqual(outcome.status, "failed")
        self.assertEqual(dependencies["tasks"].task["plan_status"], "changes_requested")
        self.assertEqual(dependencies["tasks"].task["spec_status"], "draft")
        self.assertIn("DESIGN_REPLAN_REQUIRED", {gate["code"] for gate in outcome.gates})
        self.assertEqual(dependencies["conformance"].appended[0]["status"], "yellow")

    def test_stale_external_review_head_blocks_verification(self) -> None:
        task = _task_with_external_review()
        external_review = _external_review_evidence(current_head_sha="c" * 40)
        service, _dependencies = _service(task, external_review=external_review)

        outcome = service.verify("TF-1")

        self.assertEqual(outcome.status, "failed")
        self.assertIn("EXTERNAL_LLM_REVIEW_STALE", {gate["code"] for gate in outcome.gates})

    def test_head_bound_review_allows_only_report_and_task_evidence_changes(self) -> None:
        task = _task_with_external_review()
        external_review = _external_review_evidence(
            dirty_paths=(
                ".planning/tasks/TF-1/artifacts/reviews/review.json",
                ".planning/tasks/TF-1/artifacts/reviews/review.md",
                ".planning/tasks/TF-1/task.json",
            )
        )
        service, dependencies = _service(task, external_review=external_review)

        outcome = service.verify("TF-1")

        self.assertEqual(outcome.status, "passed")
        review = dependencies["tasks"].task["test_strategy"]["external_llm"]
        self.assertEqual(review["verification_binding"]["envelope_digest"], "sha256:" + "e" * 64)
        self.assertFalse(dependencies["tasks"].task["promotion"]["reverify_required"])

    def test_task_directory_policy_mutation_is_not_exempt_from_review(self) -> None:
        task = _task_with_external_review()
        external_review = _external_review_evidence(
            dirty_paths=(
                ".planning/tasks/TF-1/artifacts/reviews/review.json",
                ".planning/tasks/TF-1/artifacts/reviews/review.md",
                ".planning/tasks/TF-1/PLAN.md",
            )
        )
        service, _dependencies = _service(task, external_review=external_review)

        outcome = service.verify("TF-1")

        self.assertEqual(outcome.status, "failed")
        self.assertIn("EXTERNAL_LLM_REVIEW_STALE", {gate["code"] for gate in outcome.gates})

    def test_scope_digest_change_blocks_verification(self) -> None:
        task = _task_with_external_review()
        external_review = _external_review_evidence(
            current_scope_digest="sha256:" + "c" * 64,
        )
        service, _dependencies = _service(task, external_review=external_review)

        outcome = service.verify("TF-1")

        self.assertEqual(outcome.status, "failed")
        self.assertIn("EXTERNAL_LLM_REVIEW_STALE", {gate["code"] for gate in outcome.gates})

    def test_verify_command_scope_mutation_is_detected_before_binding(self) -> None:
        task = _task_with_external_review()
        service, dependencies = _service(
            task,
            external_review=_external_review_evidence(),
        )
        dependencies["external_reviews"].evidence_after = _external_review_evidence(
            current_scope_digest="sha256:" + "c" * 64,
        )

        outcome = service.verify("TF-1")

        self.assertEqual(outcome.status, "failed")
        review = dependencies["tasks"].task["test_strategy"]["external_llm"]
        self.assertNotIn("verification_binding", review)

    def test_persisted_command_mutation_is_preserved_and_fails_atomic_commit(self) -> None:
        task = _task_with_external_review()
        service, dependencies = _service(
            task,
            external_review=_external_review_evidence(),
        )
        dependencies["commands"].on_run = lambda: dependencies["tasks"].task.update(
            {"verify_commands": ["python -m unreviewed"]}
        )

        outcome = service.verify("TF-1")

        self.assertEqual(outcome.status, "failed")
        self.assertIn("VERIFY_SCOPE_CHANGED", {gate["code"] for gate in outcome.gates})
        persisted = dependencies["tasks"].task
        self.assertEqual(persisted["verify_commands"], ["python -m unreviewed"])
        self.assertNotIn(
            "verification_binding",
            persisted["test_strategy"]["external_llm"],
        )

    def test_mutated_verify_path_never_overwrites_unreviewed_document(self) -> None:
        task = _task_with_external_review()
        task["docs"]["verify"] = "LOG.md"
        service, dependencies = _service(
            task,
            external_review=_external_review_evidence(),
        )

        outcome = service.verify("TF-1")

        self.assertEqual(outcome.status, "failed")
        self.assertIn("EXTERNAL_LLM_REVIEW_STALE", {gate["code"] for gate in outcome.gates})
        self.assertEqual(
            {path for path, _content in dependencies["documents"].writes},
            {"VERIFY.md"},
        )
        self.assertNotIn("LOG.md", dependencies["documents"].contents)

    def test_review_change_after_generated_outputs_invalidates_binding(self) -> None:
        task = _task_with_external_review()
        service, dependencies = _service(
            task,
            external_review=_external_review_evidence(),
        )
        dependencies["external_reviews"].evidence_after_call = 3
        dependencies["external_reviews"].evidence_after = _external_review_evidence(
            current_head_sha="c" * 40,
        )

        outcome = service.verify("TF-1")

        self.assertEqual(outcome.status, "failed")
        self.assertIn("EXTERNAL_LLM_REVIEW_STALE", {gate["code"] for gate in outcome.gates})
        self.assertNotIn(
            "verification_binding",
            dependencies["tasks"].task["test_strategy"]["external_llm"],
        )


def _service(
    task: dict,
    *,
    command_status: VerificationStatus = VerificationStatus.PASSED,
    validation_gates: tuple[dict, ...] = (),
    external_review: ExternalReviewEvidence | None = None,
) -> tuple[VerificationService, dict[str, object]]:
    dependencies = {
        "tasks": MemoryTasks(task),
        "planning_documents": PlanningDocumentsFake(),
        "documents": DocumentsFake(),
        "validation": ValidationFake(validation_gates),
        "conformance": ConformanceFake(),
        "commands": CommandsFake(command_status),
        "evidence": EvidenceFake(),
        "external_reviews": ExternalReviewsFake(external_review),
        "events": EventsFake(),
        "clock": FixedClock(),
    }
    return VerificationService(**dependencies), dependencies


def _task(*, plan_status: str = "approved") -> dict:
    return {
        "id": "TF-1",
        "type": "feature",
        "slug": "verification",
        "status": "open",
        "stage": "audit",
        "workflow_phase": "execution",
        "plan_status": plan_status,
        "plan_review_round": 0,
        "max_plan_review_rounds": 3,
        "spec_status": "frozen",
        "verify_status": "not_run",
        "audit_attempts": 0,
        "max_audit_attempts": 10,
        "gates": [],
        "docs": {"brief": "BRIEF.md", "plan": "PLAN.md", "verify": "VERIFY.md"},
        "verify_commands": ["python -m unittest"],
        "promotion": {"required": False, "reverify_required": False},
        "test_strategy": {
            "normal_cases": [{"name": "happy"}],
            "edge_cases": [{"name": "empty"}],
            "exception_cases": [{"name": "failure"}],
            "verification_methods": [{"target": "happy", "method": "unit"}],
            "external_llm": {"required": False, "status": "not_needed"},
        },
        "subtasks": [],
        "meta": {},
    }


def _task_with_external_review() -> dict:
    task = _task()
    task["worktree_path"] = "/workspace"
    task["task_dir"] = ".planning/tasks/TF-1"
    task["test_strategy"]["external_llm"] = {
        "required": True,
        "provider": "independent Codex reviewer",
        "purpose": "challenge the migration",
        "trigger": "before promotion",
        "status": "passed",
        "reviewer": "independent-codex-agent",
        "reviewed_head_sha": "a" * 40,
        "scope_digest": "sha256:" + "s" * 64,
        "envelope_path": ".planning/tasks/TF-1/artifacts/reviews/review.json",
        "envelope_digest": "sha256:" + "e" * 64,
        "report_path": ".planning/tasks/TF-1/artifacts/reviews/review.md",
        "report_digest": "sha256:" + "b" * 64,
        "finding_count": 0,
        "blocking_finding_count": 0,
        "verification_output_paths": [
            "VERIFY.md",
            "artifacts/evidence/evidence-graph.json",
        ],
        "promotion_output_paths": ["artifacts/promotion/open_pr_receipt.json"],
    }
    task["promotion"] = {"required": True, "reverify_required": True}
    return task


def _external_review_evidence(
    *,
    current_head_sha: str = "a" * 40,
    current_scope_digest: str = "sha256:" + "s" * 64,
    dirty_paths: tuple[str, ...] = (
        ".planning/tasks/TF-1/artifacts/reviews/review.json",
        ".planning/tasks/TF-1/artifacts/reviews/review.md",
    ),
) -> ExternalReviewEvidence:
    return ExternalReviewEvidence(
        envelope_path=".planning/tasks/TF-1/artifacts/reviews/review.json",
        envelope_digest="sha256:" + "e" * 64,
        envelope_size_bytes=256,
        provider="independent Codex reviewer",
        reviewer="independent-codex-agent",
        reviewed_head_sha="a" * 40,
        scope_digest="sha256:" + "s" * 64,
        report_path=".planning/tasks/TF-1/artifacts/reviews/review.md",
        report_digest="sha256:" + "b" * 64,
        report_size_bytes=128,
        summary="No blocking findings.",
        findings=(),
        current_head_sha=current_head_sha,
        current_scope_digest=current_scope_digest,
        document_digests=(),
        dirty_paths=dirty_paths,
    )


if __name__ == "__main__":
    unittest.main()
