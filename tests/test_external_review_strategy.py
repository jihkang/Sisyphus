from __future__ import annotations

from pathlib import Path
import sys
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))


from sisyphus.domain.task.strategy import sync_test_strategy_from_content  # noqa: E402


class ExternalReviewStrategyTests(unittest.TestCase):
    def test_plan_sync_preserves_evidence_when_review_policy_is_unchanged(self) -> None:
        task = {"type": "feature", "test_strategy": {"external_llm": _recorded_review()}}

        sync_test_strategy_from_content(task, _plan())

        review = task["test_strategy"]["external_llm"]
        self.assertEqual(review["status"], "passed")
        self.assertEqual(review["reviewed_head_sha"], "a" * 40)
        self.assertEqual(review["report_digest"], "sha256:" + "b" * 64)
        self.assertEqual(review["envelope_digest"], "sha256:" + "e" * 64)
        self.assertEqual(review["verification_binding"]["scope_digest"], "sha256:" + "s" * 64)

    def test_plan_sync_invalidates_evidence_when_review_policy_changes(self) -> None:
        task = {"type": "feature", "test_strategy": {"external_llm": _recorded_review()}}

        sync_test_strategy_from_content(
            task,
            _plan(provider="different independent reviewer"),
        )

        review = task["test_strategy"]["external_llm"]
        self.assertEqual(review["status"], "pending")
        self.assertNotIn("reviewed_head_sha", review)
        self.assertNotIn("report_digest", review)


def _recorded_review() -> dict:
    return {
        "required": True,
        "provider": "independent Codex reviewer",
        "purpose": "challenge dependency direction and regressions",
        "trigger": "after tests and before promotion",
        "status": "passed",
        "reviewer": "independent-codex",
        "reviewed_at": "2026-07-20T12:00:00Z",
        "reviewed_head_sha": "a" * 40,
        "scope_digest": "sha256:" + "s" * 64,
        "envelope_path": ".planning/tasks/TF-1/artifacts/reviews/review.json",
        "envelope_digest": "sha256:" + "e" * 64,
        "envelope_size_bytes": 256,
        "report_path": ".planning/tasks/TF-1/artifacts/reviews/review.md",
        "report_digest": "sha256:" + "b" * 64,
        "report_size_bytes": 128,
        "finding_count": 0,
        "blocking_finding_count": 0,
        "summary": "No blocking findings.",
        "verification_binding": {
            "envelope_digest": "sha256:" + "e" * 64,
            "report_digest": "sha256:" + "b" * 64,
            "reviewed_head_sha": "a" * 40,
            "scope_digest": "sha256:" + "s" * 64,
            "verified_at": "2026-07-20T12:00:00Z",
        },
    }


def _plan(*, provider: str = "independent Codex reviewer") -> str:
    return f"""# Plan

## Test Strategy

### Normal Cases

- [ ] happy path

### Edge Cases

- [ ] empty path

### Exception Cases

- [ ] failure path

## Verification Mapping

- `happy path` -> `unit tests`

## External LLM Review

- Required: `yes`
- Provider: `{provider}`
- Purpose: `challenge dependency direction and regressions`
- Trigger: `after tests and before promotion`
"""


if __name__ == "__main__":
    unittest.main()
