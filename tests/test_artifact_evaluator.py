from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import sys
import tempfile
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from sisyphus.artifact_evaluator import (
    FeatureChangePolicy,
    INVALIDATION_STATUS_FRESH,
    INVALIDATION_STATUS_INVALID,
    INVALIDATION_STATUS_STALE,
    evaluate_feature_change_artifact,
    evaluate_feature_task_projection,
)
from sisyphus.artifact_projection import project_feature_task
from sisyphus.artifacts import (
    ARTIFACT_STATE_PROMOTABLE,
    ARTIFACT_STATE_STALE,
    ARTIFACT_STATE_VERIFIED,
    INVARIANT_STATUS_FAILED,
    ArtifactRecord,
    ArtifactInvariantRecord,
    ArtifactRef,
    NamedSlotBinding,
    VerificationClaimRecord,
    VERIFICATION_CLAIM_STATUS_FAILED,
)
from sisyphus.audit import run_verify
from sisyphus.config import load_config
from sisyphus.planning import approve_task_plan, freeze_task_spec
from sisyphus.state import create_task_record
from sisyphus.templates import materialize_task_templates


class ArtifactEvaluatorTests(unittest.TestCase):
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
                    "- [x] Lineage drift stays stale",
                    "",
                    "### Exception Cases",
                    "",
                    "- [x] Invalid claims fail clearly",
                    "",
                    "## Verification Mapping",
                    "",
                    "- `Verified task projects a feature envelope` -> `unit_test`",
                    "- `Missing verify output stays pending` -> `unit_test`",
                    "- `Lineage drift stays stale` -> `unit_test`",
                    "- `Invalid claims fail clearly` -> `unit_test`",
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

    def _prepare_projection(self, slug: str, *, verified: bool) -> object:
        task = self._new_feature_task(slug)
        self._fill_feature_docs(task)
        approve_task_plan(self.repo_root, self.config, task["id"], reviewer="reviewer", notes="approved")
        freeze_task_spec(self.repo_root, self.config, task["id"], reviewer="reviewer", notes="frozen")
        if verified:
            run_verify(self.repo_root, self.config, task["id"])
        return project_feature_task(self.repo_root, self.config, task["id"])

    def test_verified_projection_evaluates_as_promotable(self) -> None:
        projection = self._prepare_projection("artifact-evaluator-promotable", verified=True)

        evaluation = evaluate_feature_task_projection(projection)

        self.assertEqual(evaluation.derived_state, ARTIFACT_STATE_PROMOTABLE)
        self.assertEqual(evaluation.promotion.decision, ARTIFACT_STATE_PROMOTABLE)
        self.assertEqual(evaluation.invalidation.status, INVALIDATION_STATUS_FRESH)
        self.assertFalse(evaluation.missing_requirements)

    def test_pre_verify_projection_stays_candidate_with_missing_claims(self) -> None:
        projection = self._prepare_projection("artifact-evaluator-candidate", verified=False)

        evaluation = evaluate_feature_task_projection(projection)

        self.assertEqual(evaluation.derived_state, "candidate")
        self.assertIn("verification_scope:composite", evaluation.missing_requirements)
        self.assertIn("verify_required_claims", evaluation.promotion.required_actions)
        self.assertEqual([intent.intent_kind for intent in evaluation.obligation_intents], ["verify_required_claims"])
        self.assertEqual(
            evaluation.obligation_intents[0].target_artifact,
            f"artifact://{projection.feature_change_artifact.artifact_id}",
        )
        self.assertEqual(evaluation.obligation_intents[0].missing_scopes, ("composite", "cross", "local"))
        self.assertIn("verification_scope:composite", evaluation.obligation_intents[0].reasons)
        self.assertEqual(evaluation.invalidation.status, INVALIDATION_STATUS_FRESH)

    def test_stale_child_artifact_or_lineage_mismatch_marks_projection_stale(self) -> None:
        projection = self._prepare_projection("artifact-evaluator-stale", verified=True)
        stale_implementation = replace(
            projection.implementation_artifact,
            state=ARTIFACT_STATE_STALE,
        )

        evaluation = evaluate_feature_change_artifact(
            projection.feature_change_artifact,
            slot_bindings=projection.slot_bindings,
            verification_claims=projection.verification_claims,
            artifacts=(
                projection.spec_artifact,
                stale_implementation,
                *projection.test_artifacts,
                *projection.execution_receipts,
            ),
        )

        self.assertEqual(evaluation.derived_state, ARTIFACT_STATE_STALE)
        self.assertEqual(evaluation.invalidation.status, INVALIDATION_STATUS_STALE)
        self.assertEqual(evaluation.invalidation.stale_inputs[0].artifact_id, stale_implementation.artifact_id)

    def test_stale_approval_blocks_promotable_state_when_approvals_are_required(self) -> None:
        projection = self._prepare_projection("artifact-evaluator-stale-approval", verified=True)
        stale_approval = ArtifactRecord(
            artifact_id="artifact-approval-1",
            artifact_type="approval",
            state=ARTIFACT_STATE_STALE,
        )
        bindings = replace(
            projection.slot_bindings,
            approvals=projection.slot_bindings.approvals.__class__(
                slot_name="approvals",
                artifacts=(ArtifactRef("artifact-approval-1", "approval"),),
            ),
        )

        evaluation = evaluate_feature_change_artifact(
            projection.feature_change_artifact,
            slot_bindings=bindings,
            verification_claims=projection.verification_claims,
            artifacts=(*projection.atomic_artifacts(), stale_approval),
            policy=FeatureChangePolicy(require_approvals=True),
        )

        self.assertEqual(evaluation.derived_state, ARTIFACT_STATE_STALE)
        self.assertEqual(evaluation.invalidation.status, INVALIDATION_STATUS_STALE)
        self.assertEqual(evaluation.invalidation.stale_inputs[0].artifact_id, stale_approval.artifact_id)

    def test_passed_claim_must_bind_current_spec_selected_impl_and_tests(self) -> None:
        projection = self._prepare_projection("artifact-evaluator-claim-mismatch", verified=True)
        mismatched_claim = replace(
            projection.verification_claims[0],
            dependency_refs=(
                ArtifactRef(projection.spec_artifact.artifact_id, projection.spec_artifact.artifact_type),
                ArtifactRef("artifact-old-selected", "implementation_candidate"),
            ),
        )

        evaluation = evaluate_feature_change_artifact(
            projection.feature_change_artifact,
            slot_bindings=projection.slot_bindings,
            verification_claims=(mismatched_claim,),
            artifacts=projection.atomic_artifacts(),
        )

        self.assertEqual(evaluation.derived_state, "invalid")
        self.assertIn(
            f"verification_claim_dependency_mismatch:{mismatched_claim.claim_id}",
            evaluation.promotion.blocking_reasons,
        )

    def test_failed_invariant_or_claim_evaluates_as_invalid(self) -> None:
        projection = self._prepare_projection("artifact-evaluator-invalid", verified=True)
        invalid_artifact = replace(
            projection.feature_change_artifact,
            invariants=(
                ArtifactInvariantRecord("selected-is-candidate", INVARIANT_STATUS_FAILED),
            ),
        )
        failed_claim = replace(
            projection.verification_claims[0],
            status=VERIFICATION_CLAIM_STATUS_FAILED,
        )
        invalid_bindings = replace(
            projection.slot_bindings,
            selected_implementation=NamedSlotBinding(
                slot_name="selected_implementation",
                artifact=ArtifactRef("artifact-not-a-candidate", "implementation_candidate"),
            ),
        )

        evaluation = evaluate_feature_change_artifact(
            invalid_artifact,
            slot_bindings=invalid_bindings,
            verification_claims=(failed_claim,),
            artifacts=projection.atomic_artifacts(),
        )

        self.assertEqual(evaluation.derived_state, "invalid")
        self.assertEqual(evaluation.invalidation.status, INVALIDATION_STATUS_INVALID)
        self.assertIn("selected-is-candidate", evaluation.failing_invariants)
        self.assertIn("selected_implementation_not_in_candidates", evaluation.promotion.blocking_reasons)
        self.assertIn(f"verification_claim_failed:{failed_claim.claim_id}", evaluation.promotion.blocking_reasons)


if __name__ == "__main__":
    unittest.main()
