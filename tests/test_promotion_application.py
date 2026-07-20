from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import sys
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))


from sisyphus.application.commands.promotion import (  # noqa: E402
    ExecutePromotionCommand,
    RecordMergedPullRequestCommand,
)
from sisyphus.application.ports.review import ExternalReviewEvidence  # noqa: E402
from sisyphus.application.results.artifacts import ArtifactRef  # noqa: E402
from sisyphus.application.use_cases.promotion import PromotionService  # noqa: E402
from sisyphus.domain.lifecycle import ConformanceState  # noqa: E402


class MemoryTasks:
    def __init__(self, *tasks: dict) -> None:
        self.records = {str(task["id"]): deepcopy(task) for task in tasks}
        self.saved: list[str] = []

    def load(self, task_id: str) -> dict:
        if task_id not in self.records:
            raise FileNotFoundError(task_id)
        return self.records[task_id]

    def save(self, task: dict) -> None:
        task_id = str(task["id"])
        self.records[task_id] = task
        self.saved.append(task_id)

    def update(self, task_id: str, mutator) -> dict:
        task = self.load(task_id)
        replacement = mutator(task)
        if replacement is not None:
            task = replacement
        self.save(task)
        return task

    def list(self) -> tuple[dict, ...]:
        return tuple(self.records.values())


class VersionControlFake:
    def __init__(self, *, staged_changes: bool = True) -> None:
        self.staged_changes = staged_changes
        self.calls: list[tuple[str, ...]] = []

    def workspace_exists(self, workspace: str) -> bool:
        self.calls.append(("exists", workspace))
        return workspace == "/workspace"

    def stage_all(self, workspace: str) -> None:
        self.calls.append(("stage", workspace))

    def has_staged_changes(self, workspace: str) -> bool:
        self.calls.append(("has_changes", workspace))
        return self.staged_changes

    def commit(self, workspace: str, message: str) -> str:
        self.calls.append(("commit", workspace, message))
        return "commit-sha"

    def push(self, workspace: str, remote: str, branch: str) -> None:
        self.calls.append(("push", workspace, remote, branch))

    def push_revision(
        self,
        workspace: str,
        remote: str,
        revision: str,
        branch: str,
    ) -> None:
        self.calls.append(("push_revision", workspace, remote, revision, branch))

    def remote_url(self, workspace: str, remote: str) -> str | None:
        self.calls.append(("remote_url", workspace, remote))
        return "git@github.com:jihkang/Sisyphus.git"


class PullRequestsFake:
    def __init__(self) -> None:
        self.specs = []

    def create(self, spec) -> str:
        self.specs.append(spec)
        return "https://github.com/jihkang/Sisyphus/pull/17"


class ArtifactsFake:
    def __init__(self) -> None:
        self.json_writes: list[tuple[str, str, dict[str, object]]] = []
        self.text_writes: list[tuple[str, str, str]] = []

    def write_json(self, task_id: str, relative_path: str, payload) -> ArtifactRef:
        self.json_writes.append((task_id, relative_path, deepcopy(dict(payload))))
        return ArtifactRef(relative_path)

    def write_text(self, task_id: str, relative_path: str, content: str) -> ArtifactRef:
        self.text_writes.append((task_id, relative_path, content))
        return ArtifactRef(relative_path)


class ConformanceFake:
    def snapshot(self, task: dict) -> ConformanceState:
        return ConformanceState()


class ExternalReviewsFake:
    def __init__(self, *, dirty_paths: tuple[str, ...] = ()) -> None:
        self.dirty_paths = dirty_paths
        self.inspect_calls = 0

    def scope(self, workspace: str, task: dict):
        raise AssertionError("promotion must inspect the recorded envelope")

    def inspect(
        self,
        workspace: str,
        envelope_path: str,
        task: dict,
    ) -> ExternalReviewEvidence:
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
            current_head_sha=review["reviewed_head_sha"],
            current_scope_digest=review["scope_digest"],
            document_digests=(),
            dirty_paths=self.dirty_paths,
        )


class CloseoutFake:
    def __init__(self) -> None:
        self.calls: list[tuple[str, bool]] = []

    def close(self, task_id: str, *, allow_dirty: bool):
        from sisyphus.application.ports.workflow import CloseoutResult

        self.calls.append((task_id, allow_dirty))
        return CloseoutResult(closed=True, status="closed")


class InterventionsFake:
    def __init__(self) -> None:
        self.calls: list[dict[str, str]] = []

    def required(self, **request: str) -> None:
        self.calls.append(request)


class ReopenedTasksFake:
    def __init__(self) -> None:
        self.calls: list[dict[str, str]] = []

    def publish(self, **request: str) -> None:
        self.calls.append(request)


class FixedClock:
    def now(self) -> str:
        return "2026-07-19T12:00:00Z"


class PromotionApplicationTests(unittest.TestCase):
    def test_lifecycle_gate_blocks_before_version_control_side_effects(self) -> None:
        service, dependencies = _service(_task(verify_status="not_run"))

        with self.assertRaisesRegex(ValueError, "VERIFY_REQUIRED"):
            service.execute(ExecutePromotionCommand(task_id="TF-1"))

        self.assertEqual(dependencies["version_control"].calls, [])
        task = dependencies["tasks"].load("TF-1")
        self.assertEqual(task["status"], "blocked")
        self.assertIn("VERIFY_REQUIRED", {gate["code"] for gate in task["gates"]})

    def test_execute_commits_pushes_opens_pr_and_records_each_durable_phase(self) -> None:
        service, dependencies = _service(_task())

        result = service.execute(
            ExecutePromotionCommand(
                task_id="TF-1",
                title="Promote clean boundaries",
                commit_message="Promote clean boundaries",
            )
        )

        self.assertEqual(result.status, "pr_open")
        self.assertEqual(result.commit_sha, "commit-sha")
        self.assertEqual(result.pr_number, 17)
        self.assertEqual(result.receipt.relative_path, "artifacts/promotion/open_pr_receipt.json")
        self.assertEqual(
            [call[0] for call in dependencies["version_control"].calls],
            ["exists", "remote_url", "stage", "has_changes", "commit", "push"],
        )
        self.assertEqual(dependencies["pull_requests"].specs[0].base_branch, "main")
        self.assertEqual(dependencies["pull_requests"].specs[0].head_branch, "codex/clean")
        receipts = dependencies["artifacts"].json_writes
        self.assertEqual([entry[2]["status"] for entry in receipts], ["committed", "pushed", "pr_open"])

    def test_existing_constructor_without_review_adapter_remains_valid(self) -> None:
        _service_with_adapter, dependencies = _service(_task())
        legacy_dependencies = {
            key: value
            for key, value in dependencies.items()
            if key != "external_reviews"
        }

        result = PromotionService(**legacy_dependencies).execute(
            ExecutePromotionCommand(task_id="TF-1")
        )

        self.assertEqual(result.status, "pr_open")

    def test_execute_resumes_existing_commit_without_creating_another_commit(self) -> None:
        task = _task()
        task["promotion"].update({"status": "pushed", "head_sha": "existing-sha"})
        service, dependencies = _service(task, staged_changes=False)

        result = service.execute(ExecutePromotionCommand(task_id="TF-1"))

        self.assertEqual(result.commit_sha, "existing-sha")
        self.assertNotIn("commit", [call[0] for call in dependencies["version_control"].calls])
        self.assertEqual(result.status, "pr_open")

    def test_reviewed_promotion_pushes_exact_reviewed_head_without_staging(self) -> None:
        task = _reviewed_task()
        allowed_dirty_paths = (
            task["test_strategy"]["external_llm"]["envelope_path"],
            task["test_strategy"]["external_llm"]["report_path"],
            ".planning/tasks/TF-1/task.json",
            ".planning/tasks/TF-1/VERIFY.md",
            ".planning/tasks/TF-1/artifacts/evidence/evidence-graph.json",
        )
        service, dependencies = _service(
            task,
            external_dirty_paths=allowed_dirty_paths,
        )

        result = service.execute(ExecutePromotionCommand(task_id="TF-1"))

        self.assertEqual(result.commit_sha, "a" * 40)
        self.assertEqual(
            [call[0] for call in dependencies["version_control"].calls],
            ["exists", "remote_url", "push_revision"],
        )
        self.assertEqual(
            dependencies["version_control"].calls[-1],
            ("push_revision", "/workspace", "origin", "a" * 40, "codex/clean"),
        )
        self.assertEqual(dependencies["external_reviews"].inspect_calls, 1)
        self.assertEqual(
            [entry[2]["status"] for entry in dependencies["artifacts"].json_writes],
            ["pushed", "pr_open"],
        )

    def test_reviewed_promotion_rejects_unreviewed_workspace_change(self) -> None:
        task = _reviewed_task()
        service, dependencies = _service(
            task,
            external_dirty_paths=("src/sisyphus/runtime.py",),
        )

        with self.assertRaisesRegex(ValueError, "evidence changed"):
            service.execute(ExecutePromotionCommand(task_id="TF-1"))

        self.assertEqual(
            dependencies["version_control"].calls,
            [("exists", "/workspace")],
        )
        self.assertEqual(dependencies["tasks"].load("TF-1")["verify_status"], "not_run")
        self.assertIn(
            "EXTERNAL_LLM_REVIEW_STALE",
            {gate["code"] for gate in dependencies["tasks"].load("TF-1")["gates"]},
        )

    def test_reviewed_promotion_fails_closed_without_evidence_adapter(self) -> None:
        _service_with_adapter, dependencies = _service(_reviewed_task())
        legacy_dependencies = {
            key: value
            for key, value in dependencies.items()
            if key != "external_reviews"
        }

        with self.assertRaisesRegex(ValueError, "adapter is unavailable"):
            PromotionService(**legacy_dependencies).execute(
                ExecutePromotionCommand(task_id="TF-1")
            )

        self.assertEqual(dependencies["tasks"].load("TF-1")["verify_status"], "not_run")

    def test_record_merge_retargets_verified_stacked_child_and_closes_parent(self) -> None:
        parent = _task(task_id="TF-parent")
        child = _task(task_id="TF-child")
        child.update({"status": "verified", "verify_status": "passed"})
        child["promotion"].update(
            {
                "status": "pr_open",
                "strategy": "stacked",
                "parent_task_id": "TF-parent",
                "pr_number": 16,
                "pr_url": "https://github.com/jihkang/Sisyphus/pull/16",
            }
        )
        service, dependencies = _service(parent, child)

        result = service.record_merged(
            RecordMergedPullRequestCommand(
                task_id="TF-parent",
                pr_number=17,
                title="Merge clean boundaries",
                changed_files=(
                    {"path": "src/sisyphus/application/use_cases/promotion.py", "additions": 10},
                ),
            )
        )

        self.assertTrue(result.close_attempted)
        self.assertTrue(result.closed)
        self.assertEqual(result.child_retargeted_task_ids, ("TF-child",))
        self.assertEqual(dependencies["closeout"].calls, [("TF-parent", True)])
        self.assertIn("# Changeset", dependencies["artifacts"].text_writes[0][2])
        child = dependencies["tasks"].load("TF-child")
        self.assertEqual(child["workflow_phase"], "retarget_required")
        self.assertEqual(child["verify_status"], "not_run")
        self.assertTrue(child["promotion"]["reverify_required"])
        self.assertEqual(dependencies["reopened_tasks"].calls[0]["task_id"], "TF-child")


def _service(
    *tasks: dict,
    staged_changes: bool = True,
    external_dirty_paths: tuple[str, ...] = (),
) -> tuple[PromotionService, dict[str, object]]:
    dependencies = {
        "tasks": MemoryTasks(*tasks),
        "version_control": VersionControlFake(staged_changes=staged_changes),
        "pull_requests": PullRequestsFake(),
        "artifacts": ArtifactsFake(),
        "conformance": ConformanceFake(),
        "external_reviews": ExternalReviewsFake(dirty_paths=external_dirty_paths),
        "closeout": CloseoutFake(),
        "interventions": InterventionsFake(),
        "reopened_tasks": ReopenedTasksFake(),
        "clock": FixedClock(),
    }
    return PromotionService(**dependencies), dependencies


def _task(*, task_id: str = "TF-1", verify_status: str = "passed") -> dict:
    return {
        "id": task_id,
        "type": "feature",
        "slug": "clean-boundaries",
        "status": "verified" if verify_status == "passed" else "open",
        "stage": "promotion",
        "workflow_phase": "promotion_pending",
        "plan_status": "approved",
        "plan_review_round": 0,
        "max_plan_review_rounds": 3,
        "spec_status": "frozen",
        "verify_status": verify_status,
        "gates": [],
        "worktree_path": "/workspace",
        "branch": "codex/clean",
        "base_branch": "main",
        "docs": {
            "promotion": "artifacts/promotion/merge_receipt.json",
            "changeset": "CHANGESET.md",
        },
        "promotion": {
            "required": True,
            "status": "promotion_pending",
            "strategy": "direct",
            "base_branch": "main",
            "head_branch": "codex/clean",
        },
        "meta": {},
    }


def _reviewed_task() -> dict:
    task = _task()
    task["task_dir"] = ".planning/tasks/TF-1"
    task["docs"]["verify"] = "VERIFY.md"
    review = {
        "required": True,
        "status": "passed",
        "provider": "independent Codex reviewer",
        "reviewer": "independent-codex-agent",
        "reviewed_head_sha": "a" * 40,
        "scope_digest": "sha256:" + "s" * 64,
        "envelope_path": ".planning/tasks/TF-1/artifacts/reviews/review.json",
        "envelope_digest": "sha256:" + "e" * 64,
        "report_path": ".planning/tasks/TF-1/artifacts/reviews/review.md",
        "report_digest": "sha256:" + "r" * 64,
        "finding_count": 0,
        "blocking_finding_count": 0,
    }
    review["verification_binding"] = {
        field: review[field]
        for field in (
            "envelope_digest",
            "report_digest",
            "reviewed_head_sha",
            "scope_digest",
        )
    }
    task["test_strategy"] = {"external_llm": review}
    return task


if __name__ == "__main__":
    unittest.main()
