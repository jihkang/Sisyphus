from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from taskflow.audit import run_verify
from taskflow.closeout import run_close
from taskflow.config import load_config
from taskflow.state import create_task_record, load_task_record
from taskflow.templates import materialize_task_templates


class TaskflowVerifyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.repo_root = Path(self.tempdir.name)
        (self.repo_root / ".taskflow.toml").write_text(
            "\n".join(
                [
                    'base_branch = "dev"',
                    'worktree_root = "../_worktrees"',
                    'task_dir = ".planning/tasks"',
                    'branch_prefix_feature = "feat"',
                    'branch_prefix_issue = "fix"',
                    "",
                    "[commands]",
                    'lint = "echo lint-ok"',
                    "",
                    "[verify]",
                    'default = ["lint"]',
                    'feature = ["lint"]',
                    'issue = ["lint"]',
                    "",
                ]
            ),
            encoding="utf-8",
        )
        self.config = load_config(self.repo_root)

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def _new_feature_task(self, slug: str) -> dict:
        task = create_task_record(
            repo_root=self.repo_root,
            config=self.config,
            task_type="feature",
            slug=slug,
        )
        materialize_task_templates(task)
        return task

    def test_verify_blocks_in_spec_stage_for_unfilled_feature_docs(self) -> None:
        task = self._new_feature_task("spec-check")

        outcome = run_verify(self.repo_root, self.config, task["id"])

        self.assertEqual(outcome.status, "failed")
        self.assertEqual(outcome.stage, "spec")

        reloaded, _ = load_task_record(self.repo_root, self.config.task_dir, task["id"])
        self.assertEqual(reloaded["status"], "blocked")
        self.assertEqual(reloaded["stage"], "spec")
        gate_codes = {gate["code"] for gate in reloaded["gates"]}
        self.assertIn("DOC_INCOMPLETE", gate_codes)
        self.assertIn("ACCEPTANCE_CRITERIA_MISSING", gate_codes)
        self.assertIn("SPEC_INCOMPLETE", gate_codes)
        self.assertIn("VERIFICATION_MAPPING_MISSING", gate_codes)

    def test_verify_passes_when_feature_spec_is_filled(self) -> None:
        task = self._new_feature_task("filled-feature")
        task_dir = self.repo_root / task["task_dir"]

        (task_dir / "BRIEF.md").write_text(
            "\n".join(
                [
                    "# Brief",
                    "",
                    "## Task",
                    "",
                    "- Task ID: `filled`",
                    "",
                    "## Problem",
                    "",
                    "- Need a filled brief.",
                    "",
                    "## Desired Outcome",
                    "",
                    "- Verify should pass.",
                    "",
                    "## Acceptance Criteria",
                    "",
                    "- [x] Criterion A",
                    "- [x] Criterion B",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        (task_dir / "PLAN.md").write_text(
            "\n".join(
                [
                    "# Plan",
                    "",
                    "## Implementation Plan",
                    "",
                    "1. Do the work.",
                    "",
                    "## Risks",
                    "",
                    "- Small risk.",
                    "",
                    "## Test Strategy",
                    "",
                    "### Normal Cases",
                    "",
                    "- [x] Happy path works",
                    "",
                    "### Edge Cases",
                    "",
                    "- [x] Empty payload is rejected",
                    "",
                    "### Exception Cases",
                    "",
                    "- [x] Downstream timeout is surfaced",
                    "",
                    "## Verification Mapping",
                    "",
                    "- `Happy path works` -> `unit_test`",
                    "- `Empty payload is rejected` -> `integration_test`",
                    "- `Downstream timeout is surfaced` -> `manual_check`",
                    "",
                    "## External LLM Review",
                    "",
                    "- Required: `no`",
                    "- Provider: `n/a`",
                    "- Purpose: `n/a`",
                    "- Trigger: `n/a`",
                    "",
                ]
            ),
            encoding="utf-8",
        )

        outcome = run_verify(self.repo_root, self.config, task["id"])

        self.assertEqual(outcome.status, "passed")
        self.assertEqual(outcome.stage, "done")

        reloaded, _ = load_task_record(self.repo_root, self.config.task_dir, task["id"])
        self.assertEqual(reloaded["status"], "verified")
        self.assertEqual(reloaded["verify_status"], "passed")
        self.assertEqual(reloaded["stage"], "done")
        self.assertEqual(reloaded["gates"], [])
        self.assertEqual(reloaded["last_verify_results"][0]["status"], "passed")

    def test_close_requires_verified_task(self) -> None:
        task = self._new_feature_task("close-check")

        outcome = run_close(self.repo_root, self.config, task["id"], allow_dirty=False)

        self.assertFalse(outcome.closed)
        gate_codes = {gate["code"] for gate in outcome.gates}
        self.assertIn("VERIFY_REQUIRED", gate_codes)

        reloaded, _ = load_task_record(self.repo_root, self.config.task_dir, task["id"])
        self.assertEqual(reloaded["status"], "blocked")


if __name__ == "__main__":
    unittest.main()
