from __future__ import annotations

from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from sisyphus.audit import run_verify
from sisyphus.cli import main as cli_main
from sisyphus.config import load_config
from sisyphus.domain.task.documents import render_brief, render_feature_plan
from sisyphus.mcp_core import SisyphusMcpCoreService
from sisyphus.planning import approve_task_plan, freeze_task_spec, generate_subtasks
from sisyphus.spec_validation import (
    SPEC_VALIDATION_REPORT,
    SPEC_VALIDATION_SCHEMA_VERSION,
    collect_spec_validation_gates,
    load_spec_validation_report,
    spec_validation_resource_payload,
    validate_task_spec,
)
from sisyphus.state import create_task_record, load_task_record, save_task_record
from sisyphus.templates import materialize_task_templates


class SpecValidationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.repo_root = Path(self.tempdir.name)
        (self.repo_root / ".sisyphus.toml").write_text("", encoding="utf-8")
        self.config = load_config(self.repo_root)

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def _new_task(
        self,
        slug: str,
        *,
        task_type: str = "feature",
        validation_required: bool = True,
    ) -> tuple[dict, Path]:
        task = create_task_record(
            repo_root=self.repo_root,
            config=self.config,
            task_type=task_type,
            slug=slug,
        )
        materialize_task_templates(task)
        task, task_file = load_task_record(self.repo_root, self.config.task_dir, task["id"])
        task.setdefault("meta", {})["spec_validation_required"] = validation_required
        task["meta"]["owned_paths"] = ["src/sisyphus/domain/planning"]
        save_task_record(task_file=task_file, task=task)
        return task, task_file

    def _write_valid_feature_spec(self, task: dict) -> None:
        task_dir = self.repo_root / task["task_dir"]
        (task_dir / "BRIEF.md").write_text(
            "\n".join(
                [
                    "# Brief",
                    "",
                    "## Problem",
                    "",
                    "- Generic task documents can reach lifecycle execution.",
                    "",
                    "## Desired Outcome",
                    "",
                    "- Deterministic validation rejects incomplete task contracts.",
                    "",
                    "## Acceptance Criteria",
                    "",
                    "- [ ] Concrete specs produce a persisted validation report",
                    "",
                    "## Constraints",
                    "",
                    "- Validation runs without network access.",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        (task_dir / "PLAN.md").write_text(self._valid_plan(), encoding="utf-8")

    def _valid_plan(
        self,
        *,
        design_mode: str = "light",
        layer_impact: str = "layer-touching",
        external_required: bool = False,
        include_edge_mapping: bool = True,
        waivers_only: bool = False,
    ) -> str:
        strategy_lines = [
            "## Test Strategy",
            "",
            "### Normal Cases",
            "",
            "- [ ] Concrete spec passes validation",
            "",
            "### Edge Cases",
            "",
            "- [ ] `Existing` frozen task remains compatible",
            "",
            "### Exception Cases",
            "",
            "- [ ] Malformed spec returns actionable gates",
            "",
            "## Verification Mapping",
            "",
            "- `Concrete spec passes validation` -> `tests.test_spec_validation`",
        ]
        if include_edge_mapping:
            strategy_lines.append("- `Existing frozen task remains compatible` -> `tests.test_spec_validation`")
        strategy_lines.append("- `Malformed spec returns actionable gates` -> `tests.test_spec_validation`")
        if waivers_only:
            strategy_lines = [
                "## Test Strategy",
                "",
                "- This documentation-only task has no executable behavior.",
                "",
                "## Verification Mapping",
                "",
                "- No executable verification applies to this documentation-only scope.",
                "",
                "## Validation Waivers",
                "",
                "- COVERAGE_REQUIRED: reason=documentation only; scope=test strategy",
                "- VERIFICATION_MAPPING_REQUIRED: reason=documentation only; scope=verification mapping",
            ]
        external_lines = [
            "## External LLM Review",
            "",
            f"- Required: `{'yes' if external_required else 'no'}`",
            f"- Provider: `{'n/a' if not external_required else 'codex'}`",
            f"- Purpose: `{'n/a' if not external_required else 'n/a'}`",
            f"- Trigger: `{'n/a' if not external_required else 'n/a'}`",
            "",
        ]
        return "\n".join(
            [
                "# Plan",
                "",
                "## Implementation Plan",
                "",
                "1. Build the validator and connect lifecycle gates.",
                "",
                "## Risks",
                "",
                "- Strict validation could reject underspecified tasks.",
                "",
                "## Design Evaluation",
                "",
                f"- Design Mode: `{design_mode}`",
                "- Decision Reason: `centralizes task spec validation rules`",
                "- Confidence: `high`",
                f"- Layer Impact: `{layer_impact}`",
                "- Layer Decision Reason: `connects planning and verification boundaries`",
                "- Required Design Artifacts: `none`",
                "",
                "## Design Artifacts",
                "",
                "- Connection Diagram: `n/a`",
                "- Sequence Diagram: `n/a`",
                "- Boundary Note: `validator owns deterministic spec rules`",
                "",
                *strategy_lines,
                "",
                *external_lines,
            ]
        )

    def _write_valid_issue_spec(self, task: dict) -> None:
        task_dir = self.repo_root / task["task_dir"]
        (task_dir / "BRIEF.md").write_text(
            "\n".join(
                [
                    "# Brief",
                    "",
                    "## Symptom",
                    "",
                    "- Invalid records reach the workflow.",
                    "",
                    "## Expected Behavior",
                    "",
                    "- Invalid records are rejected before execution.",
                    "",
                    "## Impact",
                    "",
                    "- Lifecycle state remains trustworthy.",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        (task_dir / "REPRO.md").write_text(
            "\n".join(
                [
                    "# Repro",
                    "",
                    "## Preconditions",
                    "",
                    "- A task record with incomplete documents exists.",
                    "",
                    "## Repro Steps",
                    "",
                    "1. Request plan approval.",
                    "",
                    "## Observed Result",
                    "",
                    "- Approval proceeds without structural validation.",
                    "",
                    "## Expected Result",
                    "",
                    "- Approval returns a validation gate.",
                    "",
                    "## Regression Test Target",
                    "",
                    "- A focused lifecycle unit test fails before the fix.",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        (task_dir / "FIX_PLAN.md").write_text(
            self._valid_plan().replace("# Plan", "# Fix Plan").replace(
                "## Implementation Plan",
                "## Root Cause Hypothesis\n\n- Planning lacks one validation authority.\n\n## Fix Strategy",
            ),
            encoding="utf-8",
        )

    def test_valid_feature_spec_persists_versioned_report(self) -> None:
        task, _ = self._new_task("valid-feature")
        self._write_valid_feature_spec(task)

        outcome = validate_task_spec(self.repo_root, self.config, task["id"])

        self.assertEqual(outcome.status, "passed")
        self.assertEqual(outcome.report["schema_version"], SPEC_VALIDATION_SCHEMA_VERSION)
        self.assertTrue(outcome.report_path.is_file())
        persisted = load_spec_validation_report(outcome.report_path.parent.parent.parent)
        self.assertEqual(persisted, outcome.report)

    def test_valid_issue_spec_passes(self) -> None:
        task, _ = self._new_task("valid-issue", task_type="issue")
        self._write_valid_issue_spec(task)

        outcome = validate_task_spec(self.repo_root, self.config, task["id"])

        self.assertEqual(outcome.status, "passed")
        self.assertEqual(outcome.gates, [])

    def test_generated_placeholders_fail_with_actionable_codes(self) -> None:
        task, _ = self._new_task("placeholder")

        outcome = validate_task_spec(self.repo_root, self.config, task["id"])

        self.assertEqual(outcome.status, "failed")
        self.assertIn("PLACEHOLDER_TEXT", outcome.report["gate_codes"])
        self.assertIn("ACCEPTANCE_CRITERIA_MISSING", outcome.report["gate_codes"])
        self.assertEqual(outcome.gates[0]["code"], "SPEC_VALIDATION_FAILED")

    def test_generated_conversation_draft_requires_plan_revision(self) -> None:
        task, _ = self._new_task("generated-draft")
        task_dir = self.repo_root / task["task_dir"]
        (task_dir / "BRIEF.md").write_text(
            render_brief(
                task,
                "Add validation",
                "Add deterministic spec validation",
                requested_slug=task["slug"],
                parent_task_id=None,
            ),
            encoding="utf-8",
        )
        (task_dir / "PLAN.md").write_text(
            render_feature_plan(task, "Add validation", "Add deterministic spec validation"),
            encoding="utf-8",
        )

        outcome = validate_task_spec(self.repo_root, self.config, task["id"])

        self.assertEqual(outcome.status, "failed")
        self.assertIn("PLACEHOLDER_TEXT", outcome.report["gate_codes"])

    def test_required_task_blocks_plan_approval_until_spec_is_valid(self) -> None:
        task, _ = self._new_task("approval-gate")

        blocked = approve_task_plan(
            self.repo_root,
            self.config,
            task["id"],
            reviewer="reviewer",
            notes="reviewed",
        )
        self.assertEqual(blocked.plan_status, "pending_review")
        self.assertEqual(blocked.task_status, "blocked")
        self.assertIn("SPEC_VALIDATION_FAILED", {gate["code"] for gate in blocked.gates})

        self._write_valid_feature_spec(task)
        approved = approve_task_plan(
            self.repo_root,
            self.config,
            task["id"],
            reviewer="reviewer",
            notes="corrected",
        )
        self.assertEqual(approved.plan_status, "approved")
        self.assertNotEqual(approved.task_status, "blocked")

    def test_valid_required_task_approves_and_freezes(self) -> None:
        task, _ = self._new_task("freeze-valid")
        self._write_valid_feature_spec(task)

        approved = approve_task_plan(self.repo_root, self.config, task["id"], reviewer="reviewer", notes=None)
        frozen = freeze_task_spec(self.repo_root, self.config, task["id"], reviewer="reviewer", notes=None)

        self.assertEqual(approved.plan_status, "approved")
        self.assertEqual(frozen.spec_status, "frozen")
        reloaded, _ = load_task_record(self.repo_root, self.config.task_dir, task["id"])
        self.assertEqual(reloaded["spec_validation"]["status"], "passed")

    def test_validated_task_does_not_use_legacy_global_placeholder_scan(self) -> None:
        task, _ = self._new_task("validator-doc-authority")
        self._write_valid_feature_spec(task)
        task_dir = self.repo_root / task["task_dir"]
        plan_path = task_dir / "PLAN.md"
        plan_path.write_text(
            plan_path.read_text(encoding="utf-8")
            + "\nThe validator rejects `Criterion 1` when it is an actual field value.\n",
            encoding="utf-8",
        )
        approve_task_plan(self.repo_root, self.config, task["id"], reviewer="reviewer", notes=None)
        freeze_task_spec(self.repo_root, self.config, task["id"], reviewer="reviewer", notes=None)

        outcome = run_verify(self.repo_root, self.config, task["id"])

        self.assertEqual(outcome.status, "passed")
        self.assertNotIn("DOC_INCOMPLETE", {gate["code"] for gate in outcome.gates})

    def test_spec_freeze_recovers_after_invalid_edit_is_corrected(self) -> None:
        task, _ = self._new_task("freeze-retry")
        self._write_valid_feature_spec(task)
        approve_task_plan(self.repo_root, self.config, task["id"], reviewer="reviewer", notes=None)
        task_dir = self.repo_root / task["task_dir"]
        (task_dir / "PLAN.md").write_text("# Plan\n\n## Implementation Plan\n\n1. Step 1\n", encoding="utf-8")

        blocked = freeze_task_spec(self.repo_root, self.config, task["id"], reviewer="reviewer", notes=None)
        self.assertEqual(blocked.spec_status, "draft")
        self.assertEqual(blocked.task_status, "blocked")

        (task_dir / "PLAN.md").write_text(self._valid_plan(), encoding="utf-8")
        frozen = freeze_task_spec(self.repo_root, self.config, task["id"], reviewer="reviewer", notes=None)
        self.assertEqual(frozen.spec_status, "frozen")
        self.assertNotEqual(frozen.task_status, "blocked")

    def test_legacy_task_is_not_retroactively_blocked(self) -> None:
        task, _ = self._new_task("legacy", validation_required=False)

        outcome = approve_task_plan(self.repo_root, self.config, task["id"], reviewer="reviewer", notes=None)

        self.assertEqual(outcome.plan_status, "approved")
        self.assertNotEqual(outcome.task_status, "blocked")

    def test_explicit_validation_enrolls_legacy_task(self) -> None:
        task, _ = self._new_task("legacy-enrolled", validation_required=False)
        validate_task_spec(self.repo_root, self.config, task["id"])

        outcome = approve_task_plan(self.repo_root, self.config, task["id"], reviewer="reviewer", notes=None)

        self.assertEqual(outcome.task_status, "blocked")
        self.assertIn("SPEC_VALIDATION_FAILED", {gate["code"] for gate in outcome.gates})

    def test_stale_report_blocks_verify_and_is_visible_in_resource(self) -> None:
        task, _ = self._new_task("stale-report")
        self._write_valid_feature_spec(task)
        approve_task_plan(self.repo_root, self.config, task["id"], reviewer="reviewer", notes=None)
        freeze_task_spec(self.repo_root, self.config, task["id"], reviewer="reviewer", notes=None)
        task_dir = self.repo_root / task["task_dir"]
        brief_path = task_dir / "BRIEF.md"
        brief_path.write_text(brief_path.read_text(encoding="utf-8") + "\n- Additional constraint.\n", encoding="utf-8")

        outcome = run_verify(self.repo_root, self.config, task["id"])
        reloaded, _ = load_task_record(self.repo_root, self.config.task_dir, task["id"])
        resource = spec_validation_resource_payload(reloaded, task_dir)

        self.assertEqual(outcome.status, "failed")
        self.assertEqual(outcome.stage, "spec")
        reloaded, _ = load_task_record(self.repo_root, self.config.task_dir, task["id"])
        self.assertEqual(reloaded["workflow_phase"], "spec_in_review")
        self.assertIn("SPEC_VALIDATION_STALE", {gate["code"] for gate in outcome.gates})
        self.assertTrue(resource["stale"])

    def test_stale_report_blocks_subtask_generation(self) -> None:
        task, _ = self._new_task("stale-subtasks")
        self._write_valid_feature_spec(task)
        approve_task_plan(self.repo_root, self.config, task["id"], reviewer="reviewer", notes=None)
        freeze_task_spec(self.repo_root, self.config, task["id"], reviewer="reviewer", notes=None)
        task_dir = self.repo_root / task["task_dir"]
        brief_path = task_dir / "BRIEF.md"
        brief_path.write_text(brief_path.read_text(encoding="utf-8") + "\n- Changed after freeze.\n", encoding="utf-8")

        outcome = generate_subtasks(self.repo_root, self.config, task["id"])

        self.assertEqual(outcome.workflow_phase, "spec_in_review")
        self.assertEqual(outcome.subtasks, [])
        reloaded, _ = load_task_record(self.repo_root, self.config.task_dir, task["id"])
        self.assertIn("SPEC_VALIDATION_STALE", {gate["code"] for gate in reloaded["gates"]})

        refreshed = validate_task_spec(self.repo_root, self.config, task["id"])
        resumed = generate_subtasks(self.repo_root, self.config, task["id"])
        self.assertEqual(refreshed.status, "passed")
        self.assertEqual(resumed.workflow_phase, "execution")
        self.assertEqual(len(resumed.subtasks), 3)
        reloaded, _ = load_task_record(self.repo_root, self.config.task_dir, task["id"])
        self.assertNotEqual(reloaded["status"], "blocked")

    def test_malformed_report_is_treated_as_missing(self) -> None:
        task, _ = self._new_task("malformed-report")
        self._write_valid_feature_spec(task)
        task_dir = self.repo_root / task["task_dir"]
        report_path = task_dir / SPEC_VALIDATION_REPORT
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text("{not json", encoding="utf-8")

        gates = collect_spec_validation_gates(
            task=task,
            task_dir=task_dir,
            action="verify",
            require_existing_report=True,
        )

        self.assertEqual([gate["code"] for gate in gates], ["SPEC_VALIDATION_MISSING"])

    def test_semantically_malformed_report_is_treated_as_missing(self) -> None:
        task, _ = self._new_task("malformed-report-shape")
        self._write_valid_feature_spec(task)
        task_dir = self.repo_root / task["task_dir"]
        report_path = task_dir / SPEC_VALIDATION_REPORT
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(
            json.dumps(
                {
                    "schema_version": SPEC_VALIDATION_SCHEMA_VERSION,
                    "task_id": task["id"],
                    "status": "passed",
                    "checked_at": "now",
                    "source_fingerprint": "not-enough",
                    "summary": {},
                    "gate_codes": [],
                    "findings": [],
                }
            ),
            encoding="utf-8",
        )

        gates = collect_spec_validation_gates(
            task=task,
            task_dir=task_dir,
            action="verify",
            require_existing_report=True,
        )

        self.assertEqual([gate["code"] for gate in gates], ["SPEC_VALIDATION_MISSING"])

    def test_report_from_another_task_is_stale(self) -> None:
        source, _ = self._new_task("report-source")
        target, _ = self._new_task("report-target")
        self._write_valid_feature_spec(source)
        self._write_valid_feature_spec(target)
        source_outcome = validate_task_spec(self.repo_root, self.config, source["id"])
        target_dir = self.repo_root / target["task_dir"]
        target_report = target_dir / SPEC_VALIDATION_REPORT
        target_report.parent.mkdir(parents=True, exist_ok=True)
        target_report.write_text(
            source_outcome.report_path.read_text(encoding="utf-8"),
            encoding="utf-8",
        )

        gates = collect_spec_validation_gates(
            task=target,
            task_dir=target_dir,
            action="verify",
            require_existing_report=True,
        )

        self.assertEqual([gate["code"] for gate in gates], ["SPEC_VALIDATION_STALE"])

    def test_document_paths_cannot_escape_the_task_directory(self) -> None:
        task, task_file = self._new_task("unsafe-doc-path")
        outside = self.repo_root / "outside.md"
        outside.write_text("private content", encoding="utf-8")
        task["docs"]["brief"] = "../../outside.md"
        save_task_record(task_file=task_file, task=task)

        outcome = validate_task_spec(self.repo_root, self.config, task["id"], persist=False)

        self.assertIn("DOC_PATH_INVALID", outcome.report["gate_codes"])
        messages = " ".join(str(item["message"]) for item in outcome.report["findings"])
        self.assertNotIn("private content", messages)

    def test_prerequisite_ids_cannot_escape_the_task_directory(self) -> None:
        task, task_file = self._new_task("unsafe-prerequisite")
        task["meta"]["prerequisite_task_ids"] = ["../../outside"]
        save_task_record(task_file=task_file, task=task)
        self._write_valid_feature_spec(task)

        outcome = validate_task_spec(self.repo_root, self.config, task["id"])

        self.assertEqual(outcome.status, "warning")
        self.assertIn("PREREQUISITE_FORMAT_INVALID", {item["code"] for item in outcome.report["findings"]})

    def test_incomplete_mapping_and_underdesigned_layer_fail(self) -> None:
        task, _ = self._new_task("invalid-design")
        self._write_valid_feature_spec(task)
        task_dir = self.repo_root / task["task_dir"]
        (task_dir / "PLAN.md").write_text(
            self._valid_plan(design_mode="none", layer_impact="layer-adding", include_edge_mapping=False),
            encoding="utf-8",
        )

        outcome = validate_task_spec(self.repo_root, self.config, task["id"])

        codes = set(outcome.report["gate_codes"])
        self.assertIn("DESIGN_MODE_INSUFFICIENT", codes)
        self.assertIn("VERIFICATION_MAPPING_INCOMPLETE", codes)

    def test_explicit_waivers_allow_documentation_only_strategy(self) -> None:
        task, _ = self._new_task("waived-docs")
        self._write_valid_feature_spec(task)
        task_dir = self.repo_root / task["task_dir"]
        (task_dir / "PLAN.md").write_text(self._valid_plan(waivers_only=True), encoding="utf-8")

        outcome = validate_task_spec(self.repo_root, self.config, task["id"])

        self.assertNotEqual(outcome.status, "failed")
        self.assertNotIn("COVERAGE_REQUIRED", outcome.report["gate_codes"])
        self.assertNotIn("VERIFICATION_MAPPING_REQUIRED", outcome.report["gate_codes"])

    def test_incomplete_external_review_policy_fails(self) -> None:
        task, _ = self._new_task("external-review")
        self._write_valid_feature_spec(task)
        task_dir = self.repo_root / task["task_dir"]
        (task_dir / "PLAN.md").write_text(self._valid_plan(external_required=True), encoding="utf-8")

        outcome = validate_task_spec(self.repo_root, self.config, task["id"])

        self.assertIn("EXTERNAL_LLM_POLICY_MISSING", outcome.report["gate_codes"])

    def test_unready_prerequisite_is_reported_as_warning(self) -> None:
        prerequisite, _ = self._new_task("prerequisite", validation_required=False)
        task, task_file = self._new_task("dependent")
        task["meta"]["prerequisite_task_ids"] = [prerequisite["id"]]
        save_task_record(task_file=task_file, task=task)
        self._write_valid_feature_spec(task)

        outcome = validate_task_spec(self.repo_root, self.config, task["id"])

        self.assertEqual(outcome.status, "warning")
        self.assertIn("PREREQUISITE_NOT_READY", {finding["code"] for finding in outcome.report["findings"]})

    def test_cli_and_mcp_expose_the_same_report_contract(self) -> None:
        task, _ = self._new_task("interfaces")
        self._write_valid_feature_spec(task)
        stdout = io.StringIO()
        with redirect_stdout(stdout):
            exit_code = cli_main(["--repo", str(self.repo_root), "spec", "validate", task["id"], "--json"])
        cli_payload = json.loads(stdout.getvalue())

        core = SisyphusMcpCoreService(self.repo_root)
        mcp_payload = core.call_tool("sisyphus.spec_validate", {"task_id": task["id"]})
        resource = core.read_resource(f"task://{task['id']}/spec-validation")

        self.assertEqual(exit_code, 0)
        self.assertEqual(cli_payload["schema_version"], SPEC_VALIDATION_SCHEMA_VERSION)
        self.assertEqual(mcp_payload["report"]["schema_version"], SPEC_VALIDATION_SCHEMA_VERSION)
        self.assertEqual(resource["status"], "passed")
        self.assertIn("sisyphus.spec_validate", {tool["name"] for tool in core.list_tools()})


if __name__ == "__main__":
    unittest.main()
