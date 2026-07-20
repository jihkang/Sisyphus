from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))


from sisyphus.application.commands.review import RecordExternalReviewCommand  # noqa: E402
from sisyphus.application.ports.review import (  # noqa: E402
    ExternalReviewEvidence,
    ExternalReviewEvidenceError,
    ExternalReviewFinding,
    ExternalReviewScopeEvidence,
)
from sisyphus.application.review_scope import external_review_scope_digest  # noqa: E402
from sisyphus.application.use_cases.external_review import ExternalReviewService  # noqa: E402
from sisyphus.composition.external_review import (  # noqa: E402
    external_review_scope,
    record_external_review,
)
from sisyphus.infra.config.loader import load_config  # noqa: E402
from sisyphus.infra.verification.external_review import (  # noqa: E402
    GitExternalReviewEvidenceAdapter,
)


HEAD_SHA = "a" * 40
ENVELOPE_PATH = ".planning/tasks/TF-1/artifacts/reviews/review.json"
REPORT_PATH = ".planning/tasks/TF-1/artifacts/reviews/review.md"


class MemoryTasks:
    def __init__(self, task: dict) -> None:
        self.task = deepcopy(task)
        self.saved = 0
        self.before_update = None

    def load(self, task_id: str) -> dict:
        if task_id != self.task["id"]:
            raise FileNotFoundError(task_id)
        return self.task

    def list(self) -> tuple[dict, ...]:
        return (self.task,)

    def save(self, task: dict) -> None:
        self.task = task
        self.saved += 1

    def update(self, task_id: str, mutator) -> dict:
        task = self.load(task_id)
        if self.before_update is not None:
            self.before_update()
        replacement = mutator(task)
        if replacement is not None:
            task = replacement
        self.save(task)
        return task


class EvidenceFake:
    def __init__(
        self,
        task: dict,
        *,
        current_head_sha: str = HEAD_SHA,
        reviewed_head_sha: str = HEAD_SHA,
        current_scope_digest: str | None = None,
        envelope_scope_digest: str | None = None,
        dirty_paths: tuple[str, ...] = (ENVELOPE_PATH, REPORT_PATH),
        findings: tuple[ExternalReviewFinding, ...] = (),
        provider: str = "independent Codex reviewer",
        changed_on_confirmation: bool = False,
    ) -> None:
        scope_digest = external_review_scope_digest(task, {})
        self.scope_evidence = ExternalReviewScopeEvidence(
            current_head_sha=current_head_sha,
            scope_digest=current_scope_digest or scope_digest,
            document_digests=(),
        )
        self.inspected = ExternalReviewEvidence(
            envelope_path=ENVELOPE_PATH,
            envelope_digest="sha256:" + "e" * 64,
            envelope_size_bytes=256,
            provider=provider,
            reviewer="independent-codex-agent",
            reviewed_head_sha=reviewed_head_sha,
            scope_digest=envelope_scope_digest or scope_digest,
            report_path=REPORT_PATH,
            report_digest="sha256:" + "b" * 64,
            report_size_bytes=128,
            summary="Independent review complete.",
            findings=findings,
            current_head_sha=current_head_sha,
            current_scope_digest=current_scope_digest or scope_digest,
            document_digests=(),
            dirty_paths=dirty_paths,
        )
        self.changed_on_confirmation = changed_on_confirmation
        self.inspect_calls = 0

    def scope(self, workspace: str, task: dict) -> ExternalReviewScopeEvidence:
        if workspace != "/workspace":
            raise AssertionError(workspace)
        return self.scope_evidence

    def inspect(
        self,
        workspace: str,
        envelope_path: str,
        task: dict,
    ) -> ExternalReviewEvidence:
        if workspace != "/workspace":
            raise AssertionError(workspace)
        if envelope_path != ENVELOPE_PATH:
            raise AssertionError(envelope_path)
        self.inspect_calls += 1
        if self.changed_on_confirmation and self.inspect_calls > 1:
            return replace(
                self.inspected,
                report_digest="sha256:" + "c" * 64,
            )
        return self.inspected


class FixedClock:
    def now(self) -> str:
        return "2026-07-20T12:00:00Z"


class ExternalReviewApplicationTests(unittest.TestCase):
    def test_pass_derives_envelope_metadata_and_invalidates_existing_verification(self) -> None:
        task = _task()
        tasks = MemoryTasks(task)
        service = ExternalReviewService(
            tasks=tasks,
            evidence=EvidenceFake(task),
            clock=FixedClock(),
        )

        result = service.record(_command())

        self.assertEqual(result.status, "passed")
        self.assertEqual(result.reviewer, "independent-codex-agent")
        review = tasks.task["test_strategy"]["external_llm"]
        self.assertEqual(review["envelope_path"], ENVELOPE_PATH)
        self.assertEqual(review["finding_count"], 0)
        self.assertEqual(
            review["verification_output_paths"],
            ["VERIFY.md", "artifacts/evidence/evidence-graph.json"],
        )
        self.assertEqual(
            review["promotion_output_paths"],
            ["artifacts/promotion/open_pr_receipt.json"],
        )
        self.assertEqual(tasks.task["verify_status"], "not_run")
        self.assertIsNone(tasks.task["last_verified_at"])
        self.assertEqual(tasks.task["last_verify_results"], [])
        self.assertTrue(tasks.task["promotion"]["reverify_required"])
        self.assertEqual({gate["code"] for gate in tasks.task["gates"]}, {"VERIFY_REQUIRED"})
        self.assertEqual(tasks.saved, 1)

    def test_scope_returns_head_and_policy_fingerprint(self) -> None:
        task = _task()
        service = ExternalReviewService(
            tasks=MemoryTasks(task),
            evidence=EvidenceFake(task),
            clock=FixedClock(),
        )

        result = service.scope("TF-1")

        self.assertEqual(result.current_head_sha, HEAD_SHA)
        self.assertEqual(result.scope_digest, external_review_scope_digest(task, {}))

    def test_scope_binds_verification_document_mapping(self) -> None:
        task = _task()
        original = external_review_scope_digest(task, {})

        task["docs"]["verify"] = "LOG.md"

        self.assertNotEqual(external_review_scope_digest(task, {}), original)

    def test_scope_rejects_colliding_generated_outputs(self) -> None:
        task = _task()
        task["promotion"]["execution_receipt_path"] = "VERIFY.md"

        with self.assertRaisesRegex(ValueError, "must not collide"):
            external_review_scope_digest(task, {})

    def test_scope_rejects_verification_document_over_evidence_graph(self) -> None:
        task = _task()
        task["docs"]["verify"] = "artifacts/evidence/evidence-graph.json"

        with self.assertRaisesRegex(ValueError, "must not collide"):
            external_review_scope_digest(task, {})

    def test_scope_rejects_verification_output_over_protected_authority(self) -> None:
        for protected_path in (
            "task.json",
            "PLAN.md",
            "artifacts",
            "artifacts/reviews/review.md",
        ):
            with self.subTest(protected_path=protected_path):
                task = _task()
                task["docs"]["verify"] = protected_path

                with self.assertRaisesRegex(ValueError, "must not collide"):
                    external_review_scope_digest(task, {})

    def test_scope_rejects_promotion_receipt_over_protected_authority(self) -> None:
        for protected_path in (
            "PLAN.md",
            "artifacts",
            "artifacts/reviews/promotion.json",
        ):
            with self.subTest(protected_path=protected_path):
                task = _task()
                task["promotion"]["execution_receipt_path"] = protected_path

                with self.assertRaisesRegex(ValueError, "must not collide"):
                    external_review_scope_digest(task, {})

    def test_rejects_review_for_a_stale_head(self) -> None:
        task = _task()
        service = ExternalReviewService(
            tasks=MemoryTasks(task),
            evidence=EvidenceFake(task, current_head_sha="c" * 40),
            clock=FixedClock(),
        )

        with self.assertRaisesRegex(ValueError, "external review is stale"):
            service.record(_command())

    def test_rejects_review_for_a_stale_scope(self) -> None:
        task = _task()
        service = ExternalReviewService(
            tasks=MemoryTasks(task),
            evidence=EvidenceFake(task, current_scope_digest="sha256:" + "c" * 64),
            clock=FixedClock(),
        )

        with self.assertRaisesRegex(ValueError, "envelope scope"):
            service.record(_command())

    def test_rejects_unreviewed_dirty_paths(self) -> None:
        task = _task()
        service = ExternalReviewService(
            tasks=MemoryTasks(task),
            evidence=EvidenceFake(
                task,
                dirty_paths=(ENVELOPE_PATH, REPORT_PATH, "src/sisyphus/runtime.py"),
            ),
            clock=FixedClock(),
        )

        with self.assertRaisesRegex(ValueError, "src/sisyphus/runtime.py"):
            service.record(_command())

    def test_rejects_evidence_that_changes_during_atomic_record_update(self) -> None:
        task = _task()
        tasks = MemoryTasks(task)
        service = ExternalReviewService(
            tasks=tasks,
            evidence=EvidenceFake(task, changed_on_confirmation=True),
            clock=FixedClock(),
        )

        with self.assertRaisesRegex(ValueError, "changed during recording"):
            service.record(_command())

        self.assertEqual(tasks.saved, 0)
        self.assertEqual(tasks.task["verify_status"], "passed")

    def test_rejects_changed_worktree_before_inspecting_the_new_location(self) -> None:
        task = _task()
        tasks = MemoryTasks(task)
        evidence = EvidenceFake(task)
        service = ExternalReviewService(
            tasks=tasks,
            evidence=evidence,
            clock=FixedClock(),
        )
        tasks.before_update = lambda: tasks.task.update(
            {"worktree_path": "/unreviewed-workspace"}
        )

        with self.assertRaisesRegex(ValueError, "worktree changed"):
            service.record(_command())

        self.assertEqual(evidence.inspect_calls, 1)
        self.assertEqual(tasks.saved, 0)

    def test_blocking_findings_derive_failed_status(self) -> None:
        task = _task()
        finding = ExternalReviewFinding(
            finding_id="P1-1",
            severity="P1",
            title="Verification bypass",
            detail="The review found a blocking bypass.",
            blocking=True,
        )
        tasks = MemoryTasks(task)
        service = ExternalReviewService(
            tasks=tasks,
            evidence=EvidenceFake(task, findings=(finding,)),
            clock=FixedClock(),
        )

        result = service.record(_command())

        self.assertEqual(result.status, "failed")
        self.assertEqual(result.blocking_finding_count, 1)
        self.assertEqual(
            {gate["code"] for gate in tasks.task["gates"]},
            {"EXTERNAL_LLM_REVIEW_REQUIRED"},
        )


class GitExternalReviewEvidenceAdapterTests(unittest.TestCase):
    def test_scope_normalizes_repo_identity_before_promotion_persists_it(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            task = _initialize_review_repo(root)
            adapter = GitExternalReviewEvidenceAdapter()
            github_remote = "git@github.com:jihkang/Sisyphus.git"
            base_sha = _git(root, "rev-parse", "main")

            with (
                mock.patch(
                    "sisyphus.infra.verification.external_review.remote_url",
                    return_value=github_remote,
                ),
                mock.patch(
                    "sisyphus.infra.verification.external_review.remote_push_urls",
                    return_value=(github_remote,),
                ),
                mock.patch(
                    "sisyphus.infra.verification.external_review.remote_branch_sha",
                    return_value=base_sha,
                ),
            ):
                before = adapter.scope(str(root), task)
                task["promotion"]["repo_full_name"] = "jihkang/Sisyphus"
                after = adapter.scope(str(root), task)

            self.assertEqual(after.scope_digest, before.scope_digest)

    def test_inspects_strict_envelope_report_scope_head_and_dirty_paths(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            task = _initialize_review_repo(root)
            adapter = GitExternalReviewEvidenceAdapter()
            scope = adapter.scope(str(root), task)
            _write_review_artifacts(root, scope=scope)

            evidence = adapter.inspect(str(root), ENVELOPE_PATH, task)

            self.assertEqual(evidence.current_head_sha, _git(root, "rev-parse", "HEAD"))
            self.assertEqual(evidence.scope_digest, scope.scope_digest)
            self.assertEqual(evidence.status, "passed")
            self.assertEqual(evidence.dirty_paths, (ENVELOPE_PATH, REPORT_PATH))
            self.assertTrue(evidence.envelope_digest.startswith("sha256:"))

    def test_scope_changes_when_base_revision_moves_without_head_change(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            task = _initialize_review_repo(root)
            adapter = GitExternalReviewEvidenceAdapter()
            original = adapter.scope(str(root), task)

            _git(root, "checkout", "main")
            (root / "BASE.txt").write_text("advanced base\n", encoding="utf-8")
            _git(root, "add", "BASE.txt")
            _git(root, "commit", "-m", "advance base")
            _git(root, "checkout", "feature/review")
            moved = adapter.scope(str(root), task)

            self.assertEqual(moved.current_head_sha, original.current_head_sha)
            self.assertNotEqual(moved.scope_digest, original.scope_digest)

    def test_scope_prefers_remote_base_and_changes_only_after_remote_moves(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "worktree"
            remote = Path(temp_dir) / "remote.git"
            root.mkdir()
            remote.mkdir()
            task = _initialize_review_repo(root)
            _git(remote, "init", "--bare")
            _git(root, "remote", "add", "origin", str(remote))
            _git(root, "push", "origin", "main")
            adapter = GitExternalReviewEvidenceAdapter()
            original = adapter.scope(str(root), task)

            _git(root, "checkout", "main")
            (root / "BASE.txt").write_text("local base only\n", encoding="utf-8")
            _git(root, "add", "BASE.txt")
            _git(root, "commit", "-m", "advance local base")
            _git(root, "checkout", "feature/review")
            local_only = adapter.scope(str(root), task)

            self.assertEqual(local_only.scope_digest, original.scope_digest)
            _git(root, "push", "origin", "main")
            remote_moved = adapter.scope(str(root), task)
            self.assertNotEqual(remote_moved.scope_digest, original.scope_digest)

    def test_scope_observes_live_remote_base_without_fetching_tracking_ref(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            directory = Path(temp_dir)
            root = directory / "reviewer"
            updater = directory / "updater"
            remote = directory / "remote.git"
            root.mkdir()
            remote.mkdir()
            task = _initialize_review_repo(root)
            _git(remote, "init", "--bare")
            _git(remote, "symbolic-ref", "HEAD", "refs/heads/main")
            _git(root, "remote", "add", "origin", str(remote))
            _git(root, "push", "origin", "main")
            adapter = GitExternalReviewEvidenceAdapter()
            original = adapter.scope(str(root), task)
            stale_tracking_sha = _git(root, "rev-parse", "refs/remotes/origin/main")

            _git(directory, "clone", str(remote), str(updater))
            _git(updater, "config", "user.email", "test@example.com")
            _git(updater, "config", "user.name", "Test")
            (updater / "REMOTE.txt").write_text("advanced remotely\n", encoding="utf-8")
            _git(updater, "add", "REMOTE.txt")
            _git(updater, "commit", "-m", "advance remote base")
            _git(updater, "push", "origin", "main")

            moved = adapter.scope(str(root), task)

            self.assertEqual(
                _git(root, "rev-parse", "refs/remotes/origin/main"),
                stale_tracking_sha,
            )
            self.assertNotEqual(moved.scope_digest, original.scope_digest)

    def test_scope_binds_remote_url_even_when_base_sha_is_unchanged(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            directory = Path(temp_dir)
            root = directory / "worktree"
            first_remote = directory / "first.git"
            second_remote = directory / "second.git"
            root.mkdir()
            first_remote.mkdir()
            second_remote.mkdir()
            task = _initialize_review_repo(root)
            _git(first_remote, "init", "--bare")
            _git(second_remote, "init", "--bare")
            _git(root, "remote", "add", "origin", str(first_remote))
            _git(root, "push", "origin", "main")
            _git(root, "push", str(second_remote), "main")
            adapter = GitExternalReviewEvidenceAdapter()
            original = adapter.scope(str(root), task)

            _git(root, "remote", "set-url", "origin", str(second_remote))
            changed = adapter.scope(str(root), task)

            self.assertNotEqual(changed.scope_digest, original.scope_digest)

    def test_scope_binds_push_url_even_when_fetch_url_and_base_are_unchanged(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            directory = Path(temp_dir)
            root = directory / "worktree"
            fetch_remote = directory / "fetch.git"
            push_remote = directory / "push.git"
            additional_push_remote = directory / "additional-push.git"
            root.mkdir()
            fetch_remote.mkdir()
            push_remote.mkdir()
            additional_push_remote.mkdir()
            task = _initialize_review_repo(root)
            _git(fetch_remote, "init", "--bare")
            _git(push_remote, "init", "--bare")
            _git(additional_push_remote, "init", "--bare")
            _git(root, "remote", "add", "origin", str(fetch_remote))
            _git(root, "push", "origin", "main")
            _git(root, "push", str(push_remote), "main")
            adapter = GitExternalReviewEvidenceAdapter()
            original = adapter.scope(str(root), task)

            _git(root, "remote", "set-url", "--push", "origin", str(push_remote))
            changed = adapter.scope(str(root), task)
            _git(
                root,
                "remote",
                "set-url",
                "--add",
                "--push",
                "origin",
                str(additional_push_remote),
            )
            expanded = adapter.scope(str(root), task)

            self.assertEqual(
                _git(root, "remote", "get-url", "origin"),
                str(fetch_remote),
            )
            self.assertNotEqual(changed.scope_digest, original.scope_digest)
            self.assertNotEqual(expanded.scope_digest, changed.scope_digest)

    def test_scope_fails_closed_when_configured_remote_cannot_be_queried(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            directory = Path(temp_dir)
            root = directory / "worktree"
            remote = directory / "remote.git"
            root.mkdir()
            remote.mkdir()
            task = _initialize_review_repo(root)
            _git(remote, "init", "--bare")
            _git(root, "remote", "add", "origin", str(remote))
            _git(root, "push", "origin", "main")
            _git(root, "remote", "set-url", "origin", str(directory / "missing.git"))

            with self.assertRaisesRegex(
                ExternalReviewEvidenceError,
                "failed to resolve remote branch",
            ):
                GitExternalReviewEvidenceAdapter().scope(str(root), task)

    def test_rejects_arbitrary_repository_file_instead_of_review_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            task = _initialize_review_repo(root)
            (root / "README.md").write_text("This is not a review.\nFAIL\n", encoding="utf-8")

            with self.assertRaisesRegex(ExternalReviewEvidenceError, "artifacts/reviews"):
                GitExternalReviewEvidenceAdapter().inspect(str(root), "README.md", task)

    def test_rejects_report_digest_mismatch_and_unknown_envelope_fields(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            task = _initialize_review_repo(root)
            adapter = GitExternalReviewEvidenceAdapter()
            scope = adapter.scope(str(root), task)
            _write_review_artifacts(root, scope=scope, report_digest="sha256:" + "0" * 64)

            with self.assertRaisesRegex(ExternalReviewEvidenceError, "report digest"):
                adapter.inspect(str(root), ENVELOPE_PATH, task)

            _write_review_artifacts(root, scope=scope, extra={"caller_verdict": "pass"})
            with self.assertRaisesRegex(ExternalReviewEvidenceError, "unknown fields"):
                adapter.inspect(str(root), ENVELOPE_PATH, task)

    def test_rejects_symlinked_envelope_and_report(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir, tempfile.TemporaryDirectory() as outside_dir:
            root = Path(temp_dir)
            outside = Path(outside_dir)
            task = _initialize_review_repo(root)
            adapter = GitExternalReviewEvidenceAdapter()
            scope = adapter.scope(str(root), task)
            _write_review_artifacts(root, scope=scope)
            envelope = root / ENVELOPE_PATH
            outside_envelope = outside / "review.json"
            outside_envelope.write_bytes(envelope.read_bytes())
            envelope.unlink()
            envelope.symlink_to(outside_envelope)

            with self.assertRaises(ExternalReviewEvidenceError):
                adapter.inspect(str(root), ENVELOPE_PATH, task)

            envelope.unlink()
            _write_review_artifacts(root, scope=scope)
            report = root / REPORT_PATH
            outside_report = outside / "review.md"
            outside_report.write_bytes(report.read_bytes())
            report.unlink()
            report.symlink_to(outside_report)
            with self.assertRaises(ExternalReviewEvidenceError):
                adapter.inspect(str(root), ENVELOPE_PATH, task)

    def test_file_repository_records_and_mirrors_strict_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            repo = root / "repo"
            worktree = root / "worktree"
            repo.mkdir()
            worktree.mkdir()
            task = _task()
            task["repo_root"] = str(repo)
            task["worktree_path"] = str(worktree)
            task_dir = repo / task["task_dir"]
            worktree_task_dir = worktree / task["task_dir"]
            task_dir.mkdir(parents=True)
            worktree_task_dir.mkdir(parents=True)
            plan = _plan_document()
            for directory in (task_dir, worktree_task_dir):
                (directory / "BRIEF.md").write_text("# Brief\n", encoding="utf-8")
                (directory / "PLAN.md").write_text(plan, encoding="utf-8")
                (directory / "task.json").write_text(
                    json.dumps(task, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8",
                )
            _git(worktree, "init", "-b", "main")
            _git(worktree, "config", "user.email", "test@example.com")
            _git(worktree, "config", "user.name", "Test")
            _git(worktree, "add", ".")
            _git(worktree, "commit", "-m", "baseline")
            _git(worktree, "checkout", "-b", "feature/review")
            config = load_config(repo)
            scope = external_review_scope(
                repo_root=repo,
                config=config,
                task_id="TF-1",
            )
            _write_review_artifacts(worktree, scope=scope)

            result = record_external_review(
                repo_root=repo,
                config=config,
                task_id="TF-1",
                envelope_path=ENVELOPE_PATH,
            )

            self.assertEqual(result.status, "passed")
            central = json.loads((task_dir / "task.json").read_text(encoding="utf-8"))
            mirrored = json.loads(
                (worktree_task_dir / "task.json").read_text(encoding="utf-8")
            )
            self.assertEqual(
                central["test_strategy"]["external_llm"]["envelope_digest"],
                result.envelope_digest,
            )
            self.assertEqual(central, mirrored)


def _task() -> dict:
    return {
        "id": "TF-1",
        "type": "feature",
        "slug": "review",
        "status": "verified",
        "stage": "done",
        "workflow_phase": "verified",
        "plan_status": "approved",
        "spec_status": "frozen",
        "verify_profile": "default",
        "verify_commands": ["python -m unittest"],
        "verify_status": "passed",
        "last_verified_at": "2026-07-20T11:00:00Z",
        "last_verify_results": [{"status": "passed"}],
        "worktree_path": "/workspace",
        "task_dir": ".planning/tasks/TF-1",
        "branch": "feature/review",
        "base_branch": "main",
        "docs": {"brief": "BRIEF.md", "plan": "PLAN.md", "verify": "VERIFY.md"},
        "gates": [
            {
                "code": "EXTERNAL_LLM_REVIEW_REQUIRED",
                "message": "required external LLM review is not complete",
                "source": "strategy",
            }
        ],
        "promotion": {
            "required": True,
            "status": "promotion_pending",
            "reverify_required": False,
            "base_branch": "main",
            "head_branch": "feature/review",
        },
        "test_strategy": {
            "normal_cases": [{"name": "normal", "checked": True}],
            "edge_cases": [{"name": "edge", "checked": True}],
            "exception_cases": [{"name": "exception", "checked": True}],
            "verification_methods": [{"target": "normal", "method": "tests"}],
            "external_llm": {
                "required": True,
                "provider": "independent Codex reviewer",
                "purpose": "challenge the migration",
                "trigger": "before promotion",
                "status": "pending",
            },
        },
    }


def _command() -> RecordExternalReviewCommand:
    return RecordExternalReviewCommand(task_id="TF-1", envelope_path=ENVELOPE_PATH)


def _initialize_review_repo(root: Path) -> dict:
    task = _task()
    task["worktree_path"] = str(root)
    _git(root, "init", "-b", "main")
    _git(root, "config", "user.email", "test@example.com")
    _git(root, "config", "user.name", "Test")
    task_dir = root / task["task_dir"]
    task_dir.mkdir(parents=True)
    (task_dir / "BRIEF.md").write_text("# Brief\n", encoding="utf-8")
    (task_dir / "PLAN.md").write_text("# Plan\n", encoding="utf-8")
    _git(root, "add", ".")
    _git(root, "commit", "-m", "baseline")
    _git(root, "checkout", "-b", "feature/review")
    return task


def _write_review_artifacts(
    root: Path,
    *,
    scope: ExternalReviewScopeEvidence,
    report_digest: str | None = None,
    extra: dict[str, object] | None = None,
) -> None:
    report = root / REPORT_PATH
    report.parent.mkdir(parents=True, exist_ok=True)
    report_content = "# Independent Review\n\nNo blocking findings.\n"
    report.write_text(report_content, encoding="utf-8")
    envelope = {
        "schema_version": "sisyphus.external_review.v1",
        "provider": "independent Codex reviewer",
        "reviewer": "independent-codex-agent",
        "reviewed_head_sha": scope.current_head_sha,
        "scope_digest": scope.scope_digest,
        "report": {
            "path": REPORT_PATH,
            "digest": report_digest or _digest(report_content.encode("utf-8")),
        },
        "summary": "No blocking findings.",
        "findings": [],
        **(extra or {}),
    }
    (root / ENVELOPE_PATH).write_text(
        json.dumps(envelope, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _plan_document() -> str:
    return """# Plan

## Test Strategy

### Normal Cases

- [x] normal

### Edge Cases

- [x] edge

### Exception Cases

- [x] exception

## Verification Mapping

- `normal` -> `tests`

## External LLM Review

- Required: `yes`
- Provider: `independent Codex reviewer`
- Purpose: `challenge the migration`
- Trigger: `before promotion`
"""


def _digest(payload: bytes) -> str:
    return f"sha256:{hashlib.sha256(payload).hexdigest()}"


def _git(root: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=root,
        capture_output=True,
        text=True,
        check=True,
    )
    return completed.stdout.strip()


if __name__ == "__main__":
    unittest.main()
