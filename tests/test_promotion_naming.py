from __future__ import annotations

from pathlib import Path
import sys
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from sisyphus.api import PromotionExecutionResult, RepositoryPromotionExecutionResult
from sisyphus.promotion import PromotionExecutionOutcome, RepositoryPromotionExecution


class PromotionNamingTests(unittest.TestCase):
    def test_repository_promotion_execution_result_keeps_legacy_alias(self) -> None:
        self.assertIs(PromotionExecutionResult, RepositoryPromotionExecutionResult)
        result = RepositoryPromotionExecutionResult(
            task_id="TF-1",
            status="pr_open",
            branch="feat/example",
            base_branch="main",
            head_branch="feat/example",
            commit_sha="abc123",
            pr_number=12,
            pr_url="https://github.com/example/repo/pull/12",
            receipt_path=Path("artifacts/promotion/open_pr_receipt.json"),
            error=None,
        )

        self.assertTrue(result.ok)
        self.assertEqual(result.head_branch, "feat/example")

    def test_repository_promotion_execution_outcome_keeps_legacy_alias(self) -> None:
        self.assertIs(PromotionExecutionOutcome, RepositoryPromotionExecution)
        outcome = RepositoryPromotionExecution(
            task_id="TF-1",
            branch="feat/example",
            base_branch="main",
            head_branch="feat/example",
            status="pr_open",
            commit_sha="abc123",
            pr_number=12,
            pr_url="https://github.com/example/repo/pull/12",
            receipt_path=Path("artifacts/promotion/open_pr_receipt.json"),
        )

        self.assertEqual(outcome.base_branch, "main")
        self.assertEqual(outcome.pr_number, 12)


if __name__ == "__main__":
    unittest.main()
