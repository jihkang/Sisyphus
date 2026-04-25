from __future__ import annotations

from pathlib import Path
import sys
import tempfile
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from sisyphus.artifact_projection import project_feature_task, project_feature_task_record
from sisyphus.artifact_snapshot import (
    DEFAULT_FEATURE_TASK_ARTIFACT_SNAPSHOT_PATH,
    FEATURE_TASK_ARTIFACT_SNAPSHOT_SCHEMA_VERSION,
    materialize_feature_task_artifact_snapshot,
    read_feature_task_artifact_snapshot,
)
from sisyphus.config import load_config
from sisyphus.planning import approve_task_plan, freeze_task_spec
from sisyphus.audit import run_verify
from sisyphus.state import create_task_record, load_task_record, save_task_record
from sisyphus.templates import materialize_task_templates


class ArtifactProjectionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.repo_root = Path(self.tempdir.name)
        (self.repo_root / ".taskflow.toml").write_text(
            "\n".join(
                [
                    'base_branch = "main"',
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

    def _fill_feature_docs(self, task: dict) -> None:
        task_dir = self.repo_root / task["task_dir"]
        (task_dir / "BRIEF.md").write_text(
            "\n".join(
                [
                    "# Brief",
                    "",
                    "## Task",
                    "",
                    f"- Task ID: `{task['id']}`",
                    "",
                    "## Problem",
                    "",
                    "- Need a reconstructable artifact projection.",
                    "",
                    "## Desired Outcome",
                    "",
                    "- Feature projection is stable.",
                    "",
                    "## Acceptance Criteria",
                    "",
                    "- [x] Projection creates a feature change envelope",
                    "- [x] Projection preserves verification evidence",
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
                    "1. Build projection.",
                    "",
                    "## Risks",
                    "",
                    "- Adapter shape could drift.",
                    "",
                    "## Test Strategy",
                    "",
                    "### Normal Cases",
                    "",
                    "- [x] Verified task projects a feature envelope",
                    "",
                    "### Edge Cases",
                    "",
                    "- [x] Missing verify output stays pending",
                    "",
                    "### Exception Cases",
                    "",
                    "- [x] Missing docs fail clearly",
                    "",
                    "## Verification Mapping",
                    "",
                    "- `Verified task projects a feature envelope` -> `unit_test`",
                    "- `Missing verify output stays pending` -> `unit_test`",
                    "- `Missing docs fail clearly` -> `unit_test`",
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

    def test_verified_feature_task_projects_reconstructable_envelope(self) -> None:
        task = self._new_feature_task("artifact-projection-verified")
        self._fill_feature_docs(task)
        approve_task_plan(self.repo_root, self.config, task["id"], reviewer="reviewer", notes="approved")
        freeze_task_spec(self.repo_root, self.config, task["id"], reviewer="reviewer", notes="frozen")
        run_verify(self.repo_root, self.config, task["id"])

        projection = project_feature_task(self.repo_root, self.config, task["id"])

        self.assertEqual(projection.feature_change_artifact.artifact_type, "feature_change")
        self.assertEqual(projection.feature_change_artifact.state, "verified")
        self.assertEqual(projection.slot_bindings.spec.slot_name, "spec")
        self.assertTrue(projection.verification_claims)
        self.assertTrue(projection.execution_receipts)
        self.assertEqual(
            [claim.scope for claim in projection.verification_claims],
            ["local", "cross", "composite"],
        )
        self.assertTrue(all(claim.based_on_input_fingerprint for claim in projection.verification_claims))
        self.assertEqual(
            len({claim.based_on_input_fingerprint for claim in projection.verification_claims}),
            3,
        )
        self.assertEqual(
            projection.feature_change_artifact.payload["slot_bindings"]["selected_implementation"]["artifact"]["artifact_id"],
            projection.implementation_artifact.artifact_id,
        )

    def test_branch_and_task_runs_project_deterministically(self) -> None:
        task = self._new_feature_task("artifact-projection-branch-metadata")
        self._fill_feature_docs(task)
        approve_task_plan(self.repo_root, self.config, task["id"], reviewer="reviewer", notes="approved")
        freeze_task_spec(self.repo_root, self.config, task["id"], reviewer="reviewer", notes="frozen")
        run_verify(self.repo_root, self.config, task["id"])

        projection = project_feature_task(self.repo_root, self.config, task["id"])

        self.assertEqual(projection.implementation_artifact.payload["branch"], task["branch"])
        self.assertEqual(projection.implementation_artifact.payload["base_branch"], task["base_branch"])
        self.assertEqual(
            [run.run_id for run in projection.task_run_refs],
            [f"{task['id']}:verify:1"],
        )
        self.assertEqual(projection.task_run_refs[0].receipt_locator, projection.execution_receipts[0].artifact_id)

    def test_feature_task_projection_snapshot_persists_artifact_envelope_and_evaluation(self) -> None:
        task = self._new_feature_task("artifact-projection-snapshot")
        self._fill_feature_docs(task)
        approve_task_plan(self.repo_root, self.config, task["id"], reviewer="reviewer", notes="approved")
        freeze_task_spec(self.repo_root, self.config, task["id"], reviewer="reviewer", notes="frozen")
        run_verify(self.repo_root, self.config, task["id"])

        materialized = materialize_feature_task_artifact_snapshot(self.repo_root, self.config, task["id"])
        persisted = read_feature_task_artifact_snapshot(self.repo_root / task["task_dir"])

        self.assertTrue(materialized.changed)
        self.assertEqual(
            materialized.snapshot_path,
            self.repo_root / task["task_dir"] / DEFAULT_FEATURE_TASK_ARTIFACT_SNAPSHOT_PATH,
        )
        self.assertIsNotNone(persisted)
        assert persisted is not None
        self.assertEqual(persisted["schema_version"], FEATURE_TASK_ARTIFACT_SNAPSHOT_SCHEMA_VERSION)
        self.assertEqual(persisted["task_id"], task["id"])
        self.assertEqual(persisted["composite"]["artifact_type"], "feature_change")
        self.assertEqual(persisted["evaluation"]["promotion"]["decision"], "promotable")
        self.assertEqual(
            [claim["scope"] for claim in persisted["verification_claims"]],
            ["local", "cross", "composite"],
        )

    def test_pre_verify_feature_task_projects_candidate_with_pending_verification_sections(self) -> None:
        task = self._new_feature_task("artifact-projection-candidate")
        self._fill_feature_docs(task)

        projection = project_feature_task(self.repo_root, self.config, task["id"])

        self.assertEqual(projection.feature_change_artifact.state, "candidate")
        self.assertEqual(projection.slot_bindings.verification_claims.artifacts, ())
        self.assertEqual(projection.execution_receipts, ())
        self.assertEqual(projection.verification_claims, ())

    def test_projection_errors_for_unsupported_type_and_missing_docs(self) -> None:
        issue_task = create_task_record(
            repo_root=self.repo_root,
            config=self.config,
            task_type="issue",
            slug="artifact-projection-issue",
        )
        materialize_task_templates(issue_task)
        issue_dir = self.repo_root / issue_task["task_dir"]

        with self.assertRaisesRegex(ValueError, "supports only feature tasks"):
            project_feature_task_record(issue_task, issue_dir)

        feature_task = self._new_feature_task("artifact-projection-missing-docs")
        task_dir = self.repo_root / feature_task["task_dir"]
        (task_dir / "PLAN.md").unlink()
        reloaded, task_file = load_task_record(self.repo_root, self.config.task_dir, feature_task["id"])
        save_task_record(task_file, reloaded)

        with self.assertRaisesRegex(FileNotFoundError, "requires existing PLAN.md"):
            project_feature_task(self.repo_root, self.config, feature_task["id"])


if __name__ == "__main__":
    unittest.main()
