from __future__ import annotations

import unittest

from sisyphus.application.commands.promotion import RecordMergedPullRequestCommand
from sisyphus.application.promotion_projection import (
    build_execution_receipt,
    build_merge_receipt,
    normalize_changed_files,
    render_changeset_markdown,
    resolve_total_count,
)


class PromotionProjectionTests(unittest.TestCase):
    def test_execution_receipt_preserves_public_shape(self) -> None:
        task = _task()

        receipt = build_execution_receipt(
            task,
            draft=True,
            written_at="2026-07-20T00:00:00Z",
        )

        self.assertEqual(receipt["status"], "pr_open")
        self.assertEqual(receipt["base_resolution"]["source"], "task_base_branch")
        self.assertEqual(receipt["commit"]["sha"], "head-sha")
        self.assertTrue(receipt["pull_request"]["draft"])

    def test_merge_projection_normalizes_counts_and_renders_changeset(self) -> None:
        changed_files = normalize_changed_files(
            (
                {
                    "path": "src/sisyphus/example.py",
                    "status": "renamed",
                    "previous_path": "src/sisyphus/old.py",
                    "additions": "4",
                    "deletions": 2,
                },
            )
        )
        receipt = build_merge_receipt(
            _task(),
            RecordMergedPullRequestCommand(
                task_id="TF-1",
                pr_number=17,
                title="Clean boundaries",
                url="https://github.com/jihkang/Sisyphus/pull/17",
            ),
            title="Clean boundaries",
            recorded_at="2026-07-20T00:00:00Z",
            changed_files=changed_files,
            additions=resolve_total_count(None, changed_files, "additions"),
            deletions=resolve_total_count(None, changed_files, "deletions"),
        )

        self.assertEqual(receipt["changes"]["additions"], 4)
        self.assertEqual(receipt["changes"]["deletions"], 2)
        markdown = render_changeset_markdown(receipt)
        self.assertIn("[#17](https://github.com/jihkang/Sisyphus/pull/17)", markdown)
        self.assertIn("from src/sisyphus/old.py", markdown)
        self.assertIn("`src`: 1 files", markdown)

    def test_changed_file_projection_rejects_missing_path(self) -> None:
        with self.assertRaisesRegex(ValueError, "non-empty `path`"):
            normalize_changed_files(({"status": "modified"},))


def _task() -> dict:
    return {
        "id": "TF-1",
        "branch": "codex/clean",
        "base_branch": "main",
        "promotion": {
            "status": "pr_open",
            "strategy": "direct",
            "base_branch": "main",
            "base_source": "task_base_branch",
            "base_reason": "promotion uses the task base branch",
            "head_branch": "codex/clean",
            "head_sha": "head-sha",
            "pr_number": 17,
            "pr_url": "https://github.com/jihkang/Sisyphus/pull/17",
        },
    }


if __name__ == "__main__":
    unittest.main()
