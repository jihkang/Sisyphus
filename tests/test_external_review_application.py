from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))


from sisyphus.application.commands.review import RecordExternalReviewCommand  # noqa: E402
from sisyphus.application.ports.review import (  # noqa: E402
    ExternalReviewEvidence,
    ExternalReviewEvidenceError,
)
from sisyphus.application.use_cases.external_review import ExternalReviewService  # noqa: E402
from sisyphus.infra.verification.external_review import (  # noqa: E402
    GitExternalReviewEvidenceAdapter,
)


HEAD_SHA = "a" * 40


class MemoryTasks:
    def __init__(self, task: dict) -> None:
        self.task = deepcopy(task)
        self.saved = 0

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
        replacement = mutator(task)
        if replacement is not None:
            task = replacement
        self.save(task)
        return task


class EvidenceFake:
    def __init__(
        self,
        *,
        head_sha: str = HEAD_SHA,
        dirty_paths: tuple[str, ...] = ("docs/reviews/external.md",),
    ) -> None:
        self.head_sha = head_sha
        self.dirty_paths = dirty_paths

    def inspect(self, workspace: str, relative_path: str) -> ExternalReviewEvidence:
        if workspace != "/workspace":
            raise AssertionError(workspace)
        return ExternalReviewEvidence(
            relative_path=relative_path,
            digest="sha256:" + "b" * 64,
            size_bytes=128,
            current_head_sha=self.head_sha,
            dirty_paths=self.dirty_paths,
        )


class FixedClock:
    def now(self) -> str:
        return "2026-07-20T12:00:00Z"


class ExternalReviewApplicationTests(unittest.TestCase):
    def test_pass_records_head_bound_evidence_without_clearing_existing_gates(self) -> None:
        tasks = MemoryTasks(_task())
        service = ExternalReviewService(tasks=tasks, evidence=EvidenceFake(), clock=FixedClock())

        result = service.record(_command())

        self.assertEqual(result.status, "passed")
        self.assertEqual(result.report_digest, "sha256:" + "b" * 64)
        review = tasks.task["test_strategy"]["external_llm"]
        self.assertEqual(review["status"], "passed")
        self.assertEqual(review["reviewed_head_sha"], HEAD_SHA)
        self.assertEqual(review["blocking_finding_count"], 0)
        self.assertEqual(tasks.task["gates"][0]["code"], "EXTERNAL_LLM_REVIEW_REQUIRED")
        self.assertEqual(tasks.saved, 1)

    def test_rejects_review_for_a_stale_head(self) -> None:
        service = ExternalReviewService(
            tasks=MemoryTasks(_task()),
            evidence=EvidenceFake(head_sha="c" * 40),
            clock=FixedClock(),
        )

        with self.assertRaisesRegex(ValueError, "external review is stale"):
            service.record(_command())

    def test_rejects_unreviewed_dirty_paths(self) -> None:
        service = ExternalReviewService(
            tasks=MemoryTasks(_task()),
            evidence=EvidenceFake(
                dirty_paths=("docs/reviews/external.md", "src/sisyphus/runtime.py")
            ),
            clock=FixedClock(),
        )

        with self.assertRaisesRegex(ValueError, "src/sisyphus/runtime.py"):
            service.record(_command())

    def test_rejects_passing_verdict_with_blocking_findings(self) -> None:
        service = ExternalReviewService(
            tasks=MemoryTasks(_task()),
            evidence=EvidenceFake(),
            clock=FixedClock(),
        )

        with self.assertRaisesRegex(ValueError, "passing external review"):
            service.record(
                replace(_command(), finding_count=1, blocking_finding_count=1)
            )

    def test_fail_verdict_is_recorded_but_does_not_satisfy_verify_gate(self) -> None:
        tasks = MemoryTasks(_task())
        service = ExternalReviewService(tasks=tasks, evidence=EvidenceFake(), clock=FixedClock())

        result = service.record(
            RecordExternalReviewCommand(
                task_id="TF-1",
                reviewer="independent-codex",
                verdict="fail",
                report_path="docs/reviews/external.md",
                reviewed_head_sha=HEAD_SHA,
                finding_count=2,
                blocking_finding_count=1,
            )
        )

        self.assertEqual(result.status, "failed")
        self.assertEqual(tasks.task["test_strategy"]["external_llm"]["status"], "failed")


class GitExternalReviewEvidenceAdapterTests(unittest.TestCase):
    def test_inspects_report_digest_head_and_dirty_paths(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _git(root, "init")
            _git(root, "config", "user.email", "test@example.com")
            _git(root, "config", "user.name", "Test")
            (root / "tracked.txt").write_text("baseline\n", encoding="utf-8")
            _git(root, "add", "tracked.txt")
            _git(root, "commit", "-m", "baseline")
            report = root / "docs" / "reviews" / "external.md"
            report.parent.mkdir(parents=True)
            report.write_text("# Independent review\n\nPASS\n", encoding="utf-8")

            evidence = GitExternalReviewEvidenceAdapter().inspect(
                str(root),
                "docs/reviews/external.md",
            )

            self.assertEqual(evidence.current_head_sha, _git(root, "rev-parse", "HEAD"))
            self.assertEqual(evidence.dirty_paths, ("docs/reviews/external.md",))
            self.assertTrue(evidence.digest.startswith("sha256:"))

    def test_rejects_symlinked_report(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            outside = root.parent / f"{root.name}-outside.md"
            outside.write_text("PASS\n", encoding="utf-8")
            try:
                (root / "review.md").symlink_to(outside)
                with self.assertRaises(ExternalReviewEvidenceError):
                    GitExternalReviewEvidenceAdapter().inspect(str(root), "review.md")
            finally:
                outside.unlink(missing_ok=True)


def _task() -> dict:
    return {
        "id": "TF-1",
        "status": "blocked",
        "worktree_path": "/workspace",
        "gates": [
            {
                "code": "EXTERNAL_LLM_REVIEW_REQUIRED",
                "message": "required external LLM review is not complete",
            }
        ],
        "test_strategy": {
            "external_llm": {
                "required": True,
                "provider": "independent Codex reviewer",
                "purpose": "challenge the migration",
                "trigger": "before promotion",
                "status": "pending",
            }
        },
    }


def _command() -> RecordExternalReviewCommand:
    return RecordExternalReviewCommand(
        task_id="TF-1",
        reviewer="independent-codex",
        verdict="pass",
        report_path="docs/reviews/external.md",
        reviewed_head_sha=HEAD_SHA,
        summary="No blocking findings.",
    )


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
