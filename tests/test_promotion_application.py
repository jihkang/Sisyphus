from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import subprocess
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
from sisyphus.application.ports.promotion import PullRequestSpec  # noqa: E402
from sisyphus.application.ports.review import ExternalReviewEvidence  # noqa: E402
from sisyphus.application.results.artifacts import ArtifactRef  # noqa: E402
from sisyphus.application.use_cases.promotion import PromotionService  # noqa: E402
from sisyphus.domain.lifecycle import ConformanceState  # noqa: E402
from sisyphus.gitops import GitOperationError  # noqa: E402
from sisyphus.infra.promotion.adapters import GithubCliPullRequestAdapter  # noqa: E402


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

    def save_promotion_state(self, task: dict) -> None:
        self.save(task)

    def update(self, task_id: str, mutator) -> dict:
        task = self.load(task_id)
        replacement = mutator(task)
        if replacement is not None:
            task = replacement
        self.save(task)
        return task

    def list(self) -> tuple[dict, ...]:
        return tuple(self.records.values())


class FailingPrStateTasks(MemoryTasks):
    def __init__(self, *tasks: dict) -> None:
        super().__init__(*tasks)
        self.fail_pr_state_save = True

    def load(self, task_id: str) -> dict:
        return deepcopy(super().load(task_id))

    def save(self, task: dict) -> None:
        promotion = task.get("promotion", {})
        if self.fail_pr_state_save and promotion.get("status") == "pr_open":
            self.fail_pr_state_save = False
            raise RuntimeError("task repository unavailable")
        super().save(deepcopy(task))


class FailingCommitStateTasks(MemoryTasks):
    def __init__(self, *tasks: dict) -> None:
        super().__init__(*tasks)
        self.fail_commit_state_save = True

    def load(self, task_id: str) -> dict:
        return deepcopy(super().load(task_id))

    def save_promotion_state(self, task: dict) -> None:
        promotion = task.get("promotion", {})
        if self.fail_commit_state_save and promotion.get("status") == "committed":
            self.fail_commit_state_save = False
            raise RuntimeError("task repository unavailable after commit")
        super().save_promotion_state(deepcopy(task))


class VersionControlFake:
    def __init__(
        self,
        *,
        staged_changes: bool = True,
        current_head_sha: str = "workspace-head-sha",
    ) -> None:
        self.staged_changes = staged_changes
        self.current_head_sha = current_head_sha
        self.dirty_path_values = ("src/change.py",) if staged_changes else ()
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
        self.staged_changes = False
        self.dirty_path_values = ()
        self.current_head_sha = "commit-sha"
        return "commit-sha"

    def current_head(self, workspace: str) -> str:
        self.calls.append(("current_head", workspace))
        return self.current_head_sha

    def dirty_paths(self, workspace: str) -> tuple[str, ...]:
        self.calls.append(("dirty_paths", workspace))
        return self.dirty_path_values

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
    def __init__(self, *, failures: int = 0, ambiguous_failures: int = 0) -> None:
        self.specs = []
        self.find_specs = []
        self.failures = failures
        self.ambiguous_failures = ambiguous_failures
        self.existing_url: str | None = None

    def find_open(self, spec) -> str | None:
        self.find_specs.append(spec)
        return self.existing_url

    def create(self, spec) -> str:
        self.specs.append(spec)
        if self.failures:
            self.failures -= 1
            raise RuntimeError("pull request API unavailable")
        self.existing_url = "https://github.com/jihkang/Sisyphus/pull/17"
        if self.ambiguous_failures:
            self.ambiguous_failures -= 1
            raise RuntimeError("pull request response was lost")
        return self.existing_url


class ArtifactsFake:
    def __init__(self, *, fail_status: str | None = None) -> None:
        self.json_writes: list[tuple[str, str, dict[str, object]]] = []
        self.text_writes: list[tuple[str, str, str]] = []
        self.fail_status = fail_status

    def write_json(self, task_id: str, relative_path: str, payload) -> ArtifactRef:
        if self.fail_status is not None and self.fail_status == payload.get("status"):
            self.fail_status = None
            raise RuntimeError("artifact store unavailable")
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

    def test_execution_receipt_cannot_overwrite_task_authority_document(self) -> None:
        task = _task()
        task["promotion"]["execution_receipt_path"] = "CHANGESET.md"
        service, dependencies = _service(task)

        with self.assertRaisesRegex(ValueError, "must not collide"):
            service.execute(ExecutePromotionCommand(task_id="TF-1"))

        self.assertNotIn(
            "stage",
            [call[0] for call in dependencies["version_control"].calls],
        )

    def test_execute_resumes_existing_commit_without_creating_another_commit(self) -> None:
        task = _task()
        task["promotion"].update({"status": "pushed", "head_sha": "existing-sha"})
        service, dependencies = _service(task, staged_changes=False)

        result = service.execute(ExecutePromotionCommand(task_id="TF-1"))

        self.assertEqual(result.commit_sha, "existing-sha")
        self.assertNotIn("commit", [call[0] for call in dependencies["version_control"].calls])
        self.assertEqual(result.status, "pr_open")

    def test_retry_does_not_commit_control_state_or_receipt_changes(self) -> None:
        task = _task()
        task["task_dir"] = ".planning/tasks/TF-1"
        task["promotion"].update(
            {
                "status": "pushed",
                "head_sha": "existing-sha",
                "pushed_at": "2026-07-19T11:00:00Z",
            }
        )
        service, dependencies = _service(task, staged_changes=True)
        dependencies["version_control"].dirty_path_values = (
            ".planning/tasks/TF-1/task.json",
            ".planning/tasks/TF-1/artifacts/promotion/open_pr_receipt.json",
        )

        result = service.execute(ExecutePromotionCommand(task_id="TF-1"))

        self.assertEqual(result.commit_sha, "existing-sha")
        calls = [call[0] for call in dependencies["version_control"].calls]
        self.assertNotIn("stage", calls)
        self.assertNotIn("commit", calls)
        self.assertNotIn("push", calls)

    def test_new_commit_from_pushed_state_is_pushed_before_pr_reuse(self) -> None:
        task = _task()
        task["promotion"].update(
            {
                "status": "pushed",
                "head_sha": "old-sha",
                "pushed_at": "2026-07-19T11:00:00Z",
            }
        )
        service, dependencies = _service(task, staged_changes=True)

        result = service.execute(ExecutePromotionCommand(task_id="TF-1"))

        self.assertEqual(result.commit_sha, "commit-sha")
        calls = [call[0] for call in dependencies["version_control"].calls]
        self.assertEqual(calls.count("commit"), 1)
        self.assertEqual(calls.count("push"), 1)

    def test_retry_finds_pr_created_before_ambiguous_api_failure(self) -> None:
        service, dependencies = _service(_task(), ambiguous_pr_failures=1)

        with self.assertRaisesRegex(RuntimeError, "response was lost"):
            service.execute(ExecutePromotionCommand(task_id="TF-1"))
        result = service.execute(ExecutePromotionCommand(task_id="TF-1"))

        self.assertEqual(result.status, "pr_open")
        self.assertEqual(len(dependencies["pull_requests"].specs), 1)
        self.assertEqual(len(dependencies["pull_requests"].find_specs), 1)

    def test_retry_finds_pr_after_pr_state_save_failure(self) -> None:
        service, dependencies = _service(_task(), fail_pr_state_save=True)

        with self.assertRaisesRegex(RuntimeError, "task repository unavailable"):
            service.execute(ExecutePromotionCommand(task_id="TF-1"))
        self.assertEqual(
            dependencies["tasks"].load("TF-1")["promotion"]["status"],
            "pushed",
        )
        result = service.execute(ExecutePromotionCommand(task_id="TF-1"))

        self.assertEqual(result.status, "pr_open")
        self.assertEqual(len(dependencies["pull_requests"].specs), 1)
        self.assertEqual(len(dependencies["pull_requests"].find_specs), 1)

    def test_retry_repairs_final_receipt_after_artifact_failure(self) -> None:
        service, dependencies = _service(_task(), artifact_fail_status="pr_open")

        with self.assertRaisesRegex(RuntimeError, "artifact store unavailable"):
            service.execute(ExecutePromotionCommand(task_id="TF-1"))
        result = service.execute(ExecutePromotionCommand(task_id="TF-1"))

        self.assertEqual(result.status, "pr_open")
        self.assertEqual(len(dependencies["pull_requests"].specs), 1)
        self.assertEqual(dependencies["artifacts"].json_writes[-1][2]["status"], "pr_open")
        calls = [call[0] for call in dependencies["version_control"].calls]
        self.assertEqual(calls.count("commit"), 1)
        self.assertEqual(calls.count("push"), 1)

    def test_retry_recovers_commit_when_commit_state_save_failed(self) -> None:
        task = _task()
        task["promotion"].update(
            {
                "status": "pushed",
                "head_sha": "old-sha",
                "pushed_at": "2026-07-19T11:00:00Z",
            }
        )
        service, dependencies = _service(
            task,
            fail_commit_state_save=True,
        )

        with self.assertRaisesRegex(RuntimeError, "after commit"):
            service.execute(ExecutePromotionCommand(task_id="TF-1"))
        dependencies["version_control"].staged_changes = False
        result = service.execute(ExecutePromotionCommand(task_id="TF-1"))

        self.assertEqual(result.commit_sha, "commit-sha")
        calls = [call[0] for call in dependencies["version_control"].calls]
        self.assertEqual(calls.count("commit"), 1)
        self.assertEqual(calls.count("push"), 1)

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

    def test_reviewed_promotion_rejects_unreviewed_integration_target_override(self) -> None:
        service, dependencies = _service(_reviewed_task())

        with self.assertRaisesRegex(ValueError, "base branch differs"):
            service.execute(
                ExecutePromotionCommand(task_id="TF-1", base_branch="release/2026")
            )

        persisted = dependencies["tasks"].load("TF-1")
        self.assertEqual(persisted["verify_status"], "not_run")
        self.assertTrue(persisted["promotion"]["reverify_required"])

    def test_reviewed_promotion_rejects_unreviewed_repository_override(self) -> None:
        service, dependencies = _service(_reviewed_task())

        with self.assertRaisesRegex(ValueError, "repository differs"):
            service.execute(
                ExecutePromotionCommand(
                    task_id="TF-1",
                    repo_full_name="other-owner/other-repo",
                )
            )

        persisted = dependencies["tasks"].load("TF-1")
        self.assertEqual(persisted["verify_status"], "not_run")
        self.assertTrue(persisted["promotion"]["reverify_required"])

    def test_reviewed_promotion_pushes_new_reviewed_sha_from_old_pushed_state(self) -> None:
        task = _reviewed_task()
        task["promotion"].update(
            {
                "status": "pushed",
                "head_sha": "old-reviewed-sha",
                "pushed_at": "2026-07-19T11:00:00Z",
            }
        )
        service, dependencies = _service(task)

        result = service.execute(ExecutePromotionCommand(task_id="TF-1"))

        self.assertEqual(result.commit_sha, "a" * 40)
        push_calls = [
            call for call in dependencies["version_control"].calls
            if call[0] == "push_revision"
        ]
        self.assertEqual(
            push_calls,
            [("push_revision", "/workspace", "origin", "a" * 40, "codex/clean")],
        )

    def test_reviewed_promotion_resumes_after_pr_failure_without_repush(self) -> None:
        task = _reviewed_task()
        allowed_dirty_paths = (
            task["test_strategy"]["external_llm"]["envelope_path"],
            task["test_strategy"]["external_llm"]["report_path"],
            ".planning/tasks/TF-1/task.json",
            ".planning/tasks/TF-1/VERIFY.md",
            ".planning/tasks/TF-1/artifacts/evidence/evidence-graph.json",
            ".planning/tasks/TF-1/artifacts/promotion/open_pr_receipt.json",
        )
        service, dependencies = _service(
            task,
            external_dirty_paths=allowed_dirty_paths,
            pr_failures=1,
        )

        with self.assertRaisesRegex(RuntimeError, "API unavailable"):
            service.execute(ExecutePromotionCommand(task_id="TF-1"))
        result = service.execute(ExecutePromotionCommand(task_id="TF-1"))

        self.assertEqual(result.status, "pr_open")
        self.assertEqual(
            [call[0] for call in dependencies["version_control"].calls].count(
                "push_revision"
            ),
            1,
        )
        self.assertEqual(len(dependencies["pull_requests"].specs), 2)

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


class PullRequestAdapterTests(unittest.TestCase):
    def test_find_open_parses_gh_json_response(self) -> None:
        calls: list[list[str]] = []

        def runner(repo_root: Path, args: list[str], *, error_prefix: str):
            calls.append(args)
            return subprocess.CompletedProcess(
                args=["gh", *args],
                returncode=0,
                stdout='[{"url":"https://github.com/jihkang/Sisyphus/pull/17"}]\n',
                stderr="",
            )

        result = GithubCliPullRequestAdapter(runner).find_open(_pull_request_spec())

        self.assertEqual(result, "https://github.com/jihkang/Sisyphus/pull/17")
        self.assertEqual(calls[0][:2], ["pr", "list"])
        self.assertIn("--head", calls[0])
        self.assertIn("--base", calls[0])

    def test_find_open_returns_none_for_empty_gh_result(self) -> None:
        def runner(repo_root: Path, args: list[str], *, error_prefix: str):
            return subprocess.CompletedProcess(
                args=["gh", *args],
                returncode=0,
                stdout="[]\n",
                stderr="",
            )

        self.assertIsNone(
            GithubCliPullRequestAdapter(runner).find_open(_pull_request_spec())
        )

    def test_find_open_rejects_malformed_gh_result(self) -> None:
        def runner(repo_root: Path, args: list[str], *, error_prefix: str):
            return subprocess.CompletedProcess(
                args=["gh", *args],
                returncode=0,
                stdout="not-json",
                stderr="",
            )

        with self.assertRaisesRegex(GitOperationError, "invalid JSON"):
            GithubCliPullRequestAdapter(runner).find_open(_pull_request_spec())


def _service(
    *tasks: dict,
    staged_changes: bool = True,
    external_dirty_paths: tuple[str, ...] = (),
    pr_failures: int = 0,
    ambiguous_pr_failures: int = 0,
    artifact_fail_status: str | None = None,
    fail_pr_state_save: bool = False,
    fail_commit_state_save: bool = False,
) -> tuple[PromotionService, dict[str, object]]:
    initial_head_sha = str(
        tasks[0].get("promotion", {}).get("head_sha") or "workspace-head-sha"
    )
    if fail_commit_state_save:
        tasks = FailingCommitStateTasks(*tasks)
    elif fail_pr_state_save:
        tasks = FailingPrStateTasks(*tasks)
    else:
        tasks = MemoryTasks(*tasks)
    dependencies = {
        "tasks": tasks,
        "version_control": VersionControlFake(
            staged_changes=staged_changes,
            current_head_sha=initial_head_sha,
        ),
        "pull_requests": PullRequestsFake(
            failures=pr_failures,
            ambiguous_failures=ambiguous_pr_failures,
        ),
        "artifacts": ArtifactsFake(fail_status=artifact_fail_status),
        "conformance": ConformanceFake(),
        "external_reviews": ExternalReviewsFake(dirty_paths=external_dirty_paths),
        "closeout": CloseoutFake(),
        "interventions": InterventionsFake(),
        "reopened_tasks": ReopenedTasksFake(),
        "clock": FixedClock(),
    }
    return PromotionService(**dependencies), dependencies


def _pull_request_spec() -> PullRequestSpec:
    return PullRequestSpec(
        workspace="/workspace",
        repo_full_name="jihkang/Sisyphus",
        base_branch="main",
        head_branch="codex/clean",
        title="Clean boundaries",
        body="Body",
        draft=False,
    )


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
        "verification_output_paths": [
            "VERIFY.md",
            "artifacts/evidence/evidence-graph.json",
        ],
        "promotion_output_paths": ["artifacts/promotion/open_pr_receipt.json"],
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
