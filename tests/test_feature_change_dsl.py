from __future__ import annotations

from pathlib import Path
import sys
import tempfile
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from sisyphus.artifact_evaluator import evaluate_feature_task_projection
from sisyphus.artifact_projection import project_feature_task
from sisyphus.config import load_config
from sisyphus.feature_change_dsl import (
    OBLIGATION_SPEC_VERIFY_COMPOSITE_FEATURE,
    compile_feature_change_obligations,
    default_feature_change_protocol_spec,
    feature_change_obligation_specs_by_id,
    obligation_intents_from_feature_change_evaluation,
)
from sisyphus.obligation_runtime import (
    OBLIGATION_STATUS_PASSED,
    build_feature_change_compiled_obligation_queue,
    execute_next_feature_change_obligation,
    materialize_feature_change_obligation_queue,
    read_feature_change_obligation_queue,
)
from sisyphus.planning import approve_task_plan, freeze_task_spec
from sisyphus.state import create_task_record, load_task_record
from sisyphus.templates import materialize_task_templates


class FeatureChangeDslTests(unittest.TestCase):
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
                    "- Need a compiled FeatureChange obligation.",
                    "",
                    "## Desired Outcome",
                    "",
                    "- The DSL compiler binds current slots.",
                    "",
                    "## Acceptance Criteria",
                    "",
                    "- [x] Composite verification obligation compiles from evaluator intent",
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
                    "1. Compile evaluator intent.",
                    "",
                    "## Risks",
                    "",
                    "- Slot selectors could leak concrete artifact state.",
                    "",
                    "## Test Strategy",
                    "",
                    "### Normal Cases",
                    "",
                    "- [x] Composite verification obligation compiles from evaluator intent",
                    "",
                    "### Edge Cases",
                    "",
                    "- [x] Optional execution receipts can be absent before verify",
                    "",
                    "### Exception Cases",
                    "",
                    "- [x] Unsupported slots fail clearly",
                    "",
                    "## Verification Mapping",
                    "",
                    "- `Composite verification obligation compiles from evaluator intent` -> `unit_test`",
                    "- `Optional execution receipts can be absent before verify` -> `unit_test`",
                    "- `Unsupported slots fail clearly` -> `unit_test`",
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

    def test_default_protocol_declares_feature_change_obligations_with_slot_input_contracts(self) -> None:
        protocol = default_feature_change_protocol_spec()
        specs = feature_change_obligation_specs_by_id(protocol)

        self.assertEqual(protocol.artifact_type, "feature_change")
        self.assertIn(OBLIGATION_SPEC_VERIFY_COMPOSITE_FEATURE, specs)
        verify_spec = specs[OBLIGATION_SPEC_VERIFY_COMPOSITE_FEATURE]
        self.assertEqual(
            [selector.ref for selector in verify_spec.input_contract.required],
            [
                "slot://spec#acceptance_criteria",
                "slot://selected_implementation",
                "slot://test_obligations",
            ],
        )
        self.assertEqual(verify_spec.execution_policy_ref, "witness_default")

    def test_evaluation_required_actions_compile_to_bound_obligations(self) -> None:
        task = self._new_feature_task("feature-change-dsl")
        self._fill_feature_docs(task)
        projection = project_feature_task(self.repo_root, self.config, task["id"])
        evaluation = evaluate_feature_task_projection(projection)

        intents = obligation_intents_from_feature_change_evaluation(evaluation)
        compiled = compile_feature_change_obligations(intents, projection)

        self.assertEqual([intent.intent_kind for intent in intents], ["verify_required_claims"])
        self.assertEqual(len(compiled), 1)
        obligation = compiled[0]
        self.assertEqual(obligation.spec_ref, OBLIGATION_SPEC_VERIFY_COMPOSITE_FEATURE)
        self.assertEqual(obligation.target_artifact, f"artifact://{projection.feature_change_artifact.artifact_id}")
        self.assertTrue(obligation.materialized_input_set.fingerprint.startswith("sha256:"))
        self.assertIn(f"artifact://{projection.spec_artifact.artifact_id}#acceptance_criteria", obligation.bound_inputs)
        self.assertIn(f"artifact://{projection.implementation_artifact.artifact_id}", obligation.bound_inputs)
        self.assertEqual(
            [item for item in obligation.bound_inputs if item.startswith("artifact://")],
            list(obligation.materialized_input_set.refs),
        )

    def test_compiled_obligation_queue_persists_task_local_runtime_instances(self) -> None:
        task = self._new_feature_task("feature-change-obligation-queue")
        self._fill_feature_docs(task)
        projection = project_feature_task(self.repo_root, self.config, task["id"])
        evaluation = evaluate_feature_task_projection(projection)

        payload = build_feature_change_compiled_obligation_queue(projection, evaluation)
        materialized = materialize_feature_change_obligation_queue(self.repo_root, self.config, task["id"])
        persisted = read_feature_change_obligation_queue(self.repo_root / task["task_dir"])

        self.assertEqual(payload["obligation_count"], 1)
        self.assertTrue(materialized.changed)
        self.assertIsNotNone(persisted)
        assert persisted is not None
        self.assertEqual(persisted["obligation_count"], 1)
        obligation = persisted["compiled_obligations"][0]
        self.assertEqual(obligation["spec_ref"], OBLIGATION_SPEC_VERIFY_COMPOSITE_FEATURE)
        self.assertTrue(obligation["materialized_input_set"]["fingerprint"].startswith("sha256:"))

    def test_pending_verification_obligation_executes_via_verify_runner(self) -> None:
        task = self._new_feature_task("feature-change-obligation-execute")
        self._fill_feature_docs(task)
        approve_task_plan(
            repo_root=self.repo_root,
            config=self.config,
            task_id=task["id"],
            reviewer="reviewer",
            notes="approved",
        )
        freeze_task_spec(
            repo_root=self.repo_root,
            config=self.config,
            task_id=task["id"],
            reviewer="reviewer",
            notes="frozen",
        )
        materialize_feature_change_obligation_queue(self.repo_root, self.config, task["id"])

        result = execute_next_feature_change_obligation(self.repo_root, self.config, task["id"])
        persisted = read_feature_change_obligation_queue(self.repo_root / task["task_dir"])
        reloaded, _ = load_task_record(self.repo_root, self.config.task_dir, task["id"])

        self.assertTrue(result.executed)
        self.assertEqual(result.status, OBLIGATION_STATUS_PASSED)
        self.assertEqual(reloaded["verify_status"], "passed")
        self.assertIsNotNone(persisted)
        assert persisted is not None
        obligation = persisted["compiled_obligations"][0]
        self.assertEqual(obligation["status"], OBLIGATION_STATUS_PASSED)
        self.assertEqual(obligation["execution_receipts"][-1]["runner"], "sisyphus.verify")


if __name__ == "__main__":
    unittest.main()
