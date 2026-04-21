from __future__ import annotations

import importlib
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from types import SimpleNamespace
from unittest import mock


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

import sisyphus
import sisyphus.cli as sisyphus_cli
from sisyphus.agents import AgentTrackingError, list_agents, register_agent, update_agent
from sisyphus.api import execute_promotion, queue_conversation, record_merged_pull_request, request_task
from sisyphus.audit import run_verify
from sisyphus.codex_prompt import build_codex_prompt
from sisyphus.conformance import append_conformance_log, summarize_task_conformance
from sisyphus.cli import (
    build_parser,
    handle_agent_run,
    handle_evolution_decide,
    handle_evolution_execute,
    handle_evolution_request_followup,
    handle_ingest_conversation,
    handle_ingest_pull_request_merged,
    handle_request,
    handle_status,
    handle_subtasks_generate,
    main as cli_main,
)
from sisyphus.closeout import run_close
from sisyphus.config import SisyphusConfig, load_config
from sisyphus.creation import TaskCreationError, create_task_workspace
from sisyphus.daemon import (
    _is_internal_sisyphus_path,
    _render_feature_plan,
    _render_issue_fix_plan,
    process_inbox_event,
    queue_conversation_event,
    queue_pull_request_merged_event,
    run_daemon,
)
from sisyphus.discovery import detect_repo_root
from sisyphus.discord_bot import build_discord_source_context, queue_discord_conversation
from sisyphus.events import new_event_envelope
from sisyphus.metrics import (
    MANUAL_INTERVENTION_REQUIRED_EVENT,
    REOPENED_AFTER_VERIFY_EVENT,
    build_value_metrics_report,
)
from sisyphus.paths import event_log_file, inbox_failed_dir, inbox_processed_dir
from sisyphus.planning import approve_task_plan, freeze_task_spec, request_plan_changes, revise_task_plan
from sisyphus.provider_wrapper import run_provider_wrapper
from sisyphus.service import TaskNotificationTracker, build_task_update_summary, run_service_step
from sisyphus.state import build_task_record, create_task_record, list_task_records, load_task_record, save_task_record
from sisyphus.templates import materialize_task_templates, template_root
from sisyphus.workflow import run_workflow_cycle


class SisyphusVerifyTests(unittest.TestCase):
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

        approve_task_plan(
            repo_root=self.repo_root,
            config=self.config,
            task_id=task["id"],
            reviewer="reviewer-1",
            notes="ready to implement",
        )
        outcome = run_verify(self.repo_root, self.config, task["id"])

        self.assertEqual(outcome.status, "passed")
        self.assertEqual(outcome.stage, "done")

        reloaded, _ = load_task_record(self.repo_root, self.config.task_dir, task["id"])
        self.assertEqual(reloaded["status"], "verified")
        self.assertEqual(reloaded["verify_status"], "passed")
        self.assertEqual(reloaded["stage"], "done")
        self.assertEqual(reloaded["workflow_phase"], "verified")
        self.assertEqual(reloaded["gates"], [])
        self.assertEqual(reloaded["last_verify_results"][0]["status"], "passed")

    def test_verify_reopens_plan_when_design_is_underdesigned(self) -> None:
        task = self._new_feature_task("design-replan")
        task_dir = self.repo_root / task["task_dir"]

        (task_dir / "BRIEF.md").write_text(
            "\n".join(
                [
                    "# Brief",
                    "",
                    "## Acceptance Criteria",
                    "",
                    "- [x] Adaptive planning state is persisted",
                    "- [x] Verify can request a design replan",
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
                    "1. Add adaptive planning state.",
                    "2. Add verify-time design evaluation.",
                    "",
                    "## Risks",
                    "",
                    "- Replanning could disturb the workflow state machine.",
                    "",
                    "## Design Evaluation",
                    "",
                    "- Design Mode: `none`",
                    "- Decision Reason: `existing contract only`",
                    "- Confidence: `medium`",
                    "- Layer Impact: `layer-adding`",
                    "- Layer Decision Reason: `introduces an adaptive planning layer`",
                    "- Required Design Artifacts: `connection_diagram, sequence_diagram`",
                    "",
                    "## Design Artifacts",
                    "",
                    "- Connection Diagram: `n/a`",
                    "- Sequence Diagram: `n/a`",
                    "- Boundary Note: `n/a`",
                    "",
                    "## Test Strategy",
                    "",
                    "### Normal Cases",
                    "",
                    "- [x] Adaptive planning state is persisted",
                    "",
                    "### Edge Cases",
                    "",
                    "- [x] Verify can reopen planning when design is too shallow",
                    "",
                    "### Exception Cases",
                    "",
                    "- [x] Existing verify flow remains actionable",
                    "",
                    "## Verification Mapping",
                    "",
                    "- `Adaptive planning state is persisted` -> `unit_test`",
                    "- `Verify can reopen planning when design is too shallow` -> `integration_test`",
                    "- `Existing verify flow remains actionable` -> `manual_check`",
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

        approve_task_plan(
            repo_root=self.repo_root,
            config=self.config,
            task_id=task["id"],
            reviewer="reviewer-1",
            notes="design needs later validation",
        )
        freeze_task_spec(
            repo_root=self.repo_root,
            config=self.config,
            task_id=task["id"],
            reviewer="reviewer-1",
            notes="freeze initial spec",
        )

        outcome = run_verify(self.repo_root, self.config, task["id"])

        self.assertEqual(outcome.status, "failed")
        self.assertEqual(outcome.stage, "plan_review")

        reloaded, _ = load_task_record(self.repo_root, self.config.task_dir, task["id"])
        gate_codes = {gate["code"] for gate in reloaded["gates"]}
        self.assertEqual(reloaded["plan_status"], "changes_requested")
        self.assertEqual(reloaded["spec_status"], "draft")
        self.assertEqual(reloaded["workflow_phase"], "plan_revision")
        self.assertEqual(reloaded["design"]["assessment"]["status"], "underdesigned")
        self.assertTrue(reloaded["design"]["assessment"]["replan_required"])
        self.assertIn("DESIGN_REPLAN_REQUIRED", gate_codes)
        self.assertIn("PLAN_CHANGES_REQUESTED", gate_codes)
        verify_text = (task_dir / "VERIFY.md").read_text(encoding="utf-8")
        self.assertIn("## Design Assessment", verify_text)
        self.assertIn("- Status: `underdesigned`", verify_text)

    def test_load_and_list_task_records_sync_docs_into_projection_state(self) -> None:
        task = self._new_feature_task("projection-sync")
        task_dir = self.repo_root / task["task_dir"]

        (task_dir / "PLAN.md").write_text(
            "\n".join(
                [
                    "# Plan",
                    "",
                    "## Implementation Plan",
                    "",
                    "1. Normalize task projections.",
                    "",
                    "## Risks",
                    "",
                    "- Projection state can drift from docs.",
                    "",
                    "## Design Evaluation",
                    "",
                    "- Design Mode: `light`",
                    "- Decision Reason: `crosses the load/list projection path`",
                    "- Confidence: `high`",
                    "- Layer Impact: `layer-touching`",
                    "- Layer Decision Reason: `MCP and CLI should read the same normalized task state`",
                    "- Required Design Artifacts: `boundary_note`",
                    "",
                    "## Design Artifacts",
                    "",
                    "- Connection Diagram: `n/a`",
                    "- Sequence Diagram: `n/a`",
                    "- Boundary Note: `docs/adaptive-planning-protocol.md`",
                    "",
                    "## Test Strategy",
                    "",
                    "### Normal Cases",
                    "",
                    "- [x] Projection surfaces doc-derived strategy",
                    "",
                    "### Edge Cases",
                    "",
                    "- [x] Placeholder docs still normalize safely",
                    "",
                    "### Exception Cases",
                    "",
                    "- [x] Missing plan sections do not crash projection loading",
                    "",
                    "## Verification Mapping",
                    "",
                    "- `Projection surfaces doc-derived strategy` -> `unit_test`",
                    "- `Placeholder docs still normalize safely` -> `unit_test`",
                    "- `Missing plan sections do not crash projection loading` -> `unit_test`",
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

        reloaded, _ = load_task_record(self.repo_root, self.config.task_dir, task["id"])
        listed = next(
            candidate
            for candidate in list_task_records(self.repo_root, self.config.task_dir)
            if candidate["id"] == task["id"]
        )

        for projected in (reloaded, listed):
            self.assertEqual(
                projected["test_strategy"]["normal_cases"][0]["name"],
                "Projection surfaces doc-derived strategy",
            )
            self.assertEqual(projected["test_strategy"]["verification_methods"][0]["method"], "unit_test")
            self.assertEqual(projected["design"]["mode"], "light")
            self.assertEqual(projected["design"]["layer_impact"], "layer-touching")
            self.assertEqual(projected["design"]["required_artifacts"], ["boundary_note"])
            self.assertEqual(
                projected["design"]["artifacts"]["boundary_note"],
                "docs/adaptive-planning-protocol.md",
            )

    def test_verify_requires_plan_approval(self) -> None:
        task = self._new_feature_task("verify-needs-plan-approval")
        task_dir = self.repo_root / task["task_dir"]

        (task_dir / "BRIEF.md").write_text(
            "\n".join(
                [
                    "# Brief",
                    "",
                    "## Acceptance Criteria",
                    "",
                    "- [x] Criterion A",
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

        self.assertEqual(outcome.status, "failed")
        self.assertEqual(outcome.stage, "plan_review")
        gate_codes = {gate["code"] for gate in outcome.gates}
        self.assertIn("PLAN_APPROVAL_REQUIRED", gate_codes)

    def test_close_requires_verified_task(self) -> None:
        task = self._new_feature_task("close-check")

        outcome = run_close(self.repo_root, self.config, task["id"], allow_dirty=False)

        self.assertFalse(outcome.closed)
        gate_codes = {gate["code"] for gate in outcome.gates}
        self.assertIn("VERIFY_REQUIRED", gate_codes)

        reloaded, _ = load_task_record(self.repo_root, self.config.task_dir, task["id"])
        self.assertEqual(reloaded["status"], "blocked")

    def test_close_allow_dirty_clears_previous_close_gate(self) -> None:
        task = self._new_feature_task("close-allow-dirty")
        task_file = self.repo_root / task["task_dir"] / "task.json"
        persisted = json.loads(task_file.read_text(encoding="utf-8"))
        persisted["status"] = "verified"
        persisted["stage"] = "done"
        persisted["verify_status"] = "passed"
        persisted["plan_status"] = "approved"
        task_file.write_text(json.dumps(persisted, indent=2) + "\n", encoding="utf-8")

        with mock.patch("sisyphus.closeout.is_dirty_worktree", return_value=True):
            blocked = run_close(self.repo_root, self.config, task["id"], allow_dirty=False)
            closed = run_close(self.repo_root, self.config, task["id"], allow_dirty=True)

        self.assertFalse(blocked.closed)
        self.assertTrue(closed.closed)
        self.assertEqual(closed.gates, [])

        reloaded, _ = load_task_record(self.repo_root, self.config.task_dir, task["id"])
        self.assertEqual(reloaded["status"], "closed")
        self.assertEqual(reloaded["gates"], [])
        self.assertTrue(reloaded["meta"]["close_override_used"])

    def test_close_blocks_on_required_promotion_and_marks_promotion_pending(self) -> None:
        task = self._new_feature_task("close-promotion-pending")
        task_file = self.repo_root / task["task_dir"] / "task.json"
        persisted = json.loads(task_file.read_text(encoding="utf-8"))
        persisted["status"] = "verified"
        persisted["stage"] = "done"
        persisted["workflow_phase"] = "verified"
        persisted["verify_status"] = "passed"
        persisted["plan_status"] = "approved"
        persisted["spec_status"] = "frozen"
        persisted["promotion"] = {
            "required": True,
            "status": "promotion_pending",
            "strategy": "direct",
            "receipt_path": persisted["docs"]["promotion"],
        }
        task_file.write_text(json.dumps(persisted, indent=2) + "\n", encoding="utf-8")

        outcome = run_close(self.repo_root, self.config, task["id"], allow_dirty=False)

        self.assertFalse(outcome.closed)
        gate_codes = {gate["code"] for gate in outcome.gates}
        self.assertIn("PROMOTION_REQUIRED", gate_codes)

        reloaded, _ = load_task_record(self.repo_root, self.config.task_dir, task["id"])
        self.assertEqual(reloaded["status"], "verified")
        self.assertEqual(reloaded["stage"], "promotion")
        self.assertEqual(reloaded["workflow_phase"], "promotion_pending")

    def test_close_succeeds_when_required_promotion_is_recorded(self) -> None:
        task = self._new_feature_task("close-promotion-recorded")
        task_file = self.repo_root / task["task_dir"] / "task.json"
        persisted = json.loads(task_file.read_text(encoding="utf-8"))
        persisted["status"] = "verified"
        persisted["stage"] = "done"
        persisted["workflow_phase"] = "verified"
        persisted["verify_status"] = "passed"
        persisted["plan_status"] = "approved"
        persisted["spec_status"] = "frozen"
        persisted["promotion"] = {
            "required": True,
            "status": "promotion_recorded",
            "strategy": "direct",
            "receipt_path": persisted["docs"]["promotion"],
        }
        task_file.write_text(json.dumps(persisted, indent=2) + "\n", encoding="utf-8")

        outcome = run_close(self.repo_root, self.config, task["id"], allow_dirty=False)

        self.assertTrue(outcome.closed)
        reloaded, _ = load_task_record(self.repo_root, self.config.task_dir, task["id"])
        self.assertEqual(reloaded["status"], "closed")
        self.assertEqual(reloaded["workflow_phase"], "closed")

    def test_load_task_record_normalizes_closed_workflow_phase(self) -> None:
        task = self._new_feature_task("closed-phase-normalization")
        task_file = self.repo_root / task["task_dir"] / "task.json"
        persisted = json.loads(task_file.read_text(encoding="utf-8"))
        persisted["status"] = "closed"
        persisted["stage"] = "done"
        persisted["workflow_phase"] = "verified"
        persisted["verify_status"] = "passed"
        persisted["closed_at"] = "2026-04-21T12:31:44Z"
        task_file.write_text(json.dumps(persisted, indent=2) + "\n", encoding="utf-8")

        reloaded, _ = load_task_record(self.repo_root, self.config.task_dir, task["id"])

        self.assertEqual(reloaded["status"], "closed")
        self.assertEqual(reloaded["stage"], "done")
        self.assertEqual(reloaded["workflow_phase"], "closed")

    def test_create_task_record_initializes_first_class_promotion_bundle(self) -> None:
        task = self._new_feature_task("promotion-defaults")

        reloaded, _ = load_task_record(self.repo_root, self.config.task_dir, task["id"])

        self.assertIn("promotion", reloaded)
        self.assertFalse(reloaded["promotion"]["required"])
        self.assertEqual(reloaded["promotion"]["status"], "not_required")
        self.assertEqual(reloaded["promotion"]["strategy"], "direct")
        self.assertEqual(reloaded["promotion"]["base_branch"], "dev")
        self.assertEqual(reloaded["promotion"]["head_branch"], task["branch"])
        self.assertEqual(reloaded["promotion"]["receipt_path"], task["docs"]["promotion"])

    def test_load_task_record_migrates_legacy_meta_promotion_to_first_class_bundle(self) -> None:
        task = self._new_feature_task("promotion-legacy")
        task_file = self.repo_root / task["task_dir"] / "task.json"
        persisted = json.loads(task_file.read_text(encoding="utf-8"))
        persisted.setdefault("meta", {})["promotion"] = {
            "status": "merged",
            "pr_number": 17,
            "url": "https://github.com/jihkang/Sisyphus/pull/17",
            "receipt_path": persisted["docs"]["promotion"],
            "changeset_path": persisted["docs"]["changeset"],
            "base_branch": "main",
            "head_branch": persisted["branch"],
            "merge_commit_sha": "abc123",
        }
        persisted.pop("promotion", None)
        task_file.write_text(json.dumps(persisted, indent=2) + "\n", encoding="utf-8")

        reloaded, _ = load_task_record(self.repo_root, self.config.task_dir, task["id"])

        self.assertTrue(reloaded["promotion"]["required"])
        self.assertEqual(reloaded["promotion"]["status"], "promotion_recorded")
        self.assertEqual(reloaded["promotion"]["pr_number"], 17)
        self.assertEqual(reloaded["promotion"]["pr_url"], "https://github.com/jihkang/Sisyphus/pull/17")
        self.assertEqual(reloaded["promotion"]["merge_commit_sha"], "abc123")
        self.assertEqual(reloaded["meta"]["promotion"]["status"], "merged")

class SisyphusNewTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.repo_root = Path(self.tempdir.name) / "repo"
        self.repo_root.mkdir(parents=True, exist_ok=True)
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
        (self.repo_root / "README.md").write_text("# test repo\n", encoding="utf-8")
        self._init_git_repo(self.repo_root, initial_branch="dev")
        self.config = load_config(self.repo_root)

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def test_create_feature_task_provisions_branch_worktree_and_docs(self) -> None:
        outcome = create_task_workspace(
            repo_root=self.repo_root,
            config=self.config,
            task_type="feature",
            slug="ship-it",
        )

        task = outcome.task
        task_dir = self.repo_root / task["task_dir"]
        worktree = Path(task["worktree_path"])

        self.assertTrue(task_dir.exists())
        self.assertTrue((task_dir / "task.json").exists())
        self.assertTrue((task_dir / "BRIEF.md").exists())
        self.assertTrue((task_dir / "PLAN.md").exists())
        self.assertTrue(worktree.is_dir())
        self.assertTrue((worktree / task["task_dir"] / "task.json").exists())
        self.assertTrue((worktree / task["task_dir"] / "BRIEF.md").exists())
        self.assertTrue((worktree / task["task_dir"] / "PLAN.md").exists())
        self.assertEqual(self._git("branch", "--show-current", cwd=worktree), task["branch"])
        self.assertEqual(self._git("rev-parse", "dev"), self._git("rev-parse", task["branch"]))
        self.assertIn(worktree.as_posix(), self._git("worktree", "list").replace("\\", "/"))

    def test_create_issue_task_uses_default_config_and_prefix(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            repo_root = Path(tempdir) / "repo"
            repo_root.mkdir(parents=True, exist_ok=True)
            (repo_root / "README.md").write_text("# default config repo\n", encoding="utf-8")
            self._init_git_repo(repo_root, initial_branch="main")
            config = load_config(repo_root)

            outcome = create_task_workspace(
                repo_root=repo_root,
                config=config,
                task_type="issue",
                slug="bugfix",
            )

            task = outcome.task
            self.assertEqual(task["branch"], "fix/bugfix")
            self.assertEqual(task["base_branch"], "main")
            self.assertTrue(Path(task["worktree_path"]).is_dir())
            self.assertEqual(self._git("rev-parse", "main", cwd=repo_root), self._git("rev-parse", task["branch"], cwd=repo_root))

    def test_create_task_fails_when_branch_exists(self) -> None:
        self._run_git(self.repo_root, "branch", "feat/existing", "dev")
        preview = build_task_record(self.repo_root, self.config, "feature", "existing")

        with self.assertRaises(TaskCreationError):
            create_task_workspace(
                repo_root=self.repo_root,
                config=self.config,
                task_type="feature",
                slug="existing",
            )

        self.assertFalse((self.repo_root / preview["task_dir"]).exists())
        self.assertFalse(Path(preview["worktree_path"]).exists())

    def test_create_task_fails_when_worktree_path_exists(self) -> None:
        preview = build_task_record(self.repo_root, self.config, "feature", "occupied")
        Path(preview["worktree_path"]).mkdir(parents=True, exist_ok=False)

        with self.assertRaises(TaskCreationError):
            create_task_workspace(
                repo_root=self.repo_root,
                config=self.config,
                task_type="feature",
                slug="occupied",
            )

        self.assertFalse((self.repo_root / preview["task_dir"]).exists())

    def test_create_task_reports_existing_task_details_when_task_dir_exists(self) -> None:
        outcome = create_task_workspace(
            repo_root=self.repo_root,
            config=self.config,
            task_type="feature",
            slug="ship-it",
        )

        with self.assertRaises(TaskCreationError) as ctx:
            create_task_workspace(
                repo_root=self.repo_root,
                config=self.config,
                task_type="feature",
                slug="ship-it",
            )

        message = str(ctx.exception)
        self.assertIn(f"task already exists: {outcome.task['id']}", message)
        self.assertIn("status: open", message)
        self.assertIn(f"branch: {outcome.task['branch']}", message)
        self.assertIn("use a new slug to create another task", message)

    def test_create_task_rolls_back_on_template_failure(self) -> None:
        preview = build_task_record(self.repo_root, self.config, "feature", "rollback-check")

        with mock.patch("sisyphus.creation.materialize_task_templates", side_effect=RuntimeError("boom")):
            with self.assertRaises(TaskCreationError):
                create_task_workspace(
                    repo_root=self.repo_root,
                    config=self.config,
                    task_type="feature",
                    slug="rollback-check",
                )

        self.assertFalse((self.repo_root / preview["task_dir"]).exists())
        self.assertFalse(Path(preview["worktree_path"]).exists())
        self.assertEqual(self._run_git(self.repo_root, "show-ref", "--verify", "--quiet", f"refs/heads/{preview['branch']}", check=False).returncode, 1)

    def _init_git_repo(self, repo_root: Path, initial_branch: str) -> None:
        self._run_git(repo_root, "init", "-b", initial_branch)
        self._run_git(repo_root, "config", "user.email", "test@example.com")
        self._run_git(repo_root, "config", "user.name", "Test User")
        self._run_git(repo_root, "add", ".")
        self._run_git(repo_root, "commit", "-m", "initial")

    def _git(self, *args: str, cwd: Path | None = None) -> str:
        completed = self._run_git(cwd or self.repo_root, *args)
        return completed.stdout.strip()

    def _run_git(self, cwd: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["git", *args],
            cwd=cwd,
            check=check,
            capture_output=True,
            text=True,
        )


class SisyphusAgentTests(unittest.TestCase):
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
                    "[verify]",
                    'default = []',
                    "",
                ]
            ),
            encoding="utf-8",
        )
        self.config = load_config(self.repo_root)
        self.task = create_task_record(
            repo_root=self.repo_root,
            config=self.config,
            task_type="feature",
            slug="agent-visibility",
        )
        materialize_task_templates(self.task)
        approve_task_plan(
            repo_root=self.repo_root,
            config=self.config,
            task_id=self.task["id"],
            reviewer="reviewer-1",
            notes="approved for execution",
        )
        freeze_task_spec(
            repo_root=self.repo_root,
            config=self.config,
            task_id=self.task["id"],
            reviewer="reviewer-1",
            notes="spec frozen",
        )

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def test_register_and_list_agents_for_task(self) -> None:
        register_agent(
            repo_root=self.repo_root,
            config=self.config,
            task_id=self.task["id"],
            agent_id="worker-1",
            role="worker",
            current_step="editing tests",
            last_message_summary="updating agent tests",
            owned_paths=["tests/test_sisyphus.py"],
        )

        agents = list_agents(
            repo_root=self.repo_root,
            config=self.config,
            task_id=self.task["id"],
        )

        self.assertEqual(len(agents), 1)
        self.assertEqual(agents[0]["agent_id"], "worker-1")
        self.assertEqual(agents[0]["status"], "running")
        self.assertEqual(agents[0]["owned_paths"], ["tests/test_sisyphus.py"])

    def test_update_and_finish_agent(self) -> None:
        register_agent(
            repo_root=self.repo_root,
            config=self.config,
            task_id=self.task["id"],
            agent_id="worker-2",
            role="explorer",
        )

        update_agent(
            repo_root=self.repo_root,
            config=self.config,
            task_id=self.task["id"],
            agent_id="worker-2",
            status="waiting",
            current_step="waiting for review",
            last_message_summary="blocked on main task",
        )
        finished = update_agent(
            repo_root=self.repo_root,
            config=self.config,
            task_id=self.task["id"],
            agent_id="worker-2",
            status="failed",
            error="timeout",
        )

        self.assertEqual(finished["status"], "failed")
        self.assertEqual(finished["error"], "timeout")
        self.assertIsNotNone(finished["finished_at"])

    def test_active_agent_becomes_stale_when_heartbeat_is_old(self) -> None:
        register_agent(
            repo_root=self.repo_root,
            config=self.config,
            task_id=self.task["id"],
            agent_id="worker-3",
            role="worker",
        )
        agent_file = self.repo_root / self.task["task_dir"] / "agents" / "worker-3.json"
        persisted = json.loads(agent_file.read_text(encoding="utf-8"))
        persisted["updated_at"] = "2000-01-01T00:00:00Z"
        persisted["last_heartbeat_at"] = "2000-01-01T00:00:00Z"
        agent_file.write_text(json.dumps(persisted, indent=2) + "\n", encoding="utf-8")

        agents = list_agents(
            repo_root=self.repo_root,
            config=self.config,
            task_id=self.task["id"],
            stale_after_seconds=60,
        )

        self.assertEqual(agents[0]["status"], "stale")
        self.assertEqual(agents[0]["raw_status"], "running")

    def test_update_agent_rejects_unknown_fields_via_guard(self) -> None:
        register_agent(
            repo_root=self.repo_root,
            config=self.config,
            task_id=self.task["id"],
            agent_id="worker-guard",
            role="worker",
        )

        with self.assertRaises(AgentTrackingError):
            update_agent(
                repo_root=self.repo_root,
                config=self.config,
                task_id=self.task["id"],
                agent_id="worker-guard",
                unsupported_field="boom",
            )

    def test_status_output_includes_agent_summary(self) -> None:
        register_agent(
            repo_root=self.repo_root,
            config=self.config,
            task_id=self.task["id"],
            agent_id="worker-4",
            role="worker",
            current_step="implementing registry",
        )
        register_agent(
            repo_root=self.repo_root,
            config=self.config,
            task_id=self.task["id"],
            agent_id="worker-5",
            role="explorer",
            status="queued",
        )
        update_agent(
            repo_root=self.repo_root,
            config=self.config,
            task_id=self.task["id"],
            agent_id="worker-5",
            status="completed",
        )

        with mock.patch("sisyphus.cli.Path.cwd", return_value=self.repo_root):
            buffer = io.StringIO()
            with redirect_stdout(buffer):
                exit_code = handle_status(
                    as_json=False,
                    only_open=False,
                    only_blocked=False,
                    show_agents=True,
                    stale_after_seconds=900,
                )

        rendered = buffer.getvalue()
        self.assertEqual(exit_code, 0)
        self.assertIn("agents=2 active=1", rendered)
        self.assertIn("worker-4 provider=n/a role=worker status=running step=implementing registry", rendered)
        self.assertIn("worker-5 provider=n/a role=explorer status=completed step=-", rendered)

    def test_agent_run_marks_completed_automatically(self) -> None:
        with mock.patch("sisyphus.cli.Path.cwd", return_value=self.repo_root):
            exit_code = handle_agent_run(
                task_id=self.task["id"],
                agent_id="worker-run-ok",
                role="worker",
                provider="codex",
                step="running codex wrapper",
                summary="spawned by wrapper",
                owned_paths=["src/sisyphus/agents.py"],
                heartbeat_seconds=1,
                command=[sys.executable, "-c", "print('final success summary'); import sys; sys.exit(0)"],
            )

        agents = list_agents(
            repo_root=self.repo_root,
            config=self.config,
            task_id=self.task["id"],
        )
        completed = next(agent for agent in agents if agent["agent_id"] == "worker-run-ok")
        self.assertEqual(exit_code, 0)
        self.assertEqual(completed["status"], "completed")
        self.assertEqual(completed["provider"], "codex")
        self.assertEqual(completed["error"], None)
        self.assertEqual(completed["pid"], None)
        self.assertEqual(completed["command"][0], sys.executable)
        self.assertIn("final success summary", completed["last_message_summary"])

    def test_agent_run_marks_failed_automatically(self) -> None:
        with mock.patch("sisyphus.cli.Path.cwd", return_value=self.repo_root):
            exit_code = handle_agent_run(
                task_id=self.task["id"],
                agent_id="worker-run-fail",
                role="worker",
                provider="claude",
                step="running claude wrapper",
                summary="spawned by wrapper",
                owned_paths=None,
                heartbeat_seconds=1,
                command=[sys.executable, "-c", "import sys; sys.exit(3)"],
            )

        agents = list_agents(
            repo_root=self.repo_root,
            config=self.config,
            task_id=self.task["id"],
        )
        failed = next(agent for agent in agents if agent["agent_id"] == "worker-run-fail")
        self.assertEqual(exit_code, 3)
        self.assertEqual(failed["status"], "failed")
        self.assertEqual(failed["provider"], "claude")
        self.assertIn("code 3", failed["error"])

    def test_agent_run_requires_plan_approval(self) -> None:
        task = create_task_record(
            repo_root=self.repo_root,
            config=self.config,
            task_type="feature",
            slug="agent-review-block",
        )
        materialize_task_templates(task)

        with mock.patch("sisyphus.cli.Path.cwd", return_value=self.repo_root):
            exit_code = handle_agent_run(
                task_id=task["id"],
                agent_id="worker-blocked",
                role="worker",
                provider="codex",
                step=None,
                summary=None,
                owned_paths=None,
                heartbeat_seconds=1,
                command=[sys.executable, "-c", "print('should not run')"],
            )

        self.assertEqual(exit_code, 1)
        agents = list_agents(
            repo_root=self.repo_root,
            config=self.config,
            task_id=task["id"],
        )
        self.assertEqual(agents, [])
        persisted, _ = load_task_record(self.repo_root, self.config.task_dir, task["id"])
        gate_codes = {gate["code"] for gate in persisted["gates"]}
        self.assertIn("PLAN_APPROVAL_REQUIRED", gate_codes)

    def test_agent_run_requires_spec_freeze(self) -> None:
        task = create_task_record(
            repo_root=self.repo_root,
            config=self.config,
            task_type="feature",
            slug="spec-freeze-block",
        )
        materialize_task_templates(task)
        approve_task_plan(
            repo_root=self.repo_root,
            config=self.config,
            task_id=task["id"],
            reviewer="reviewer-1",
            notes="plan approved",
        )

        with mock.patch("sisyphus.cli.Path.cwd", return_value=self.repo_root):
            exit_code = handle_agent_run(
                task_id=task["id"],
                agent_id="worker-spec-blocked",
                role="worker",
                provider="codex",
                step=None,
                summary=None,
                owned_paths=None,
                heartbeat_seconds=1,
                command=[sys.executable, "-c", "print('should not run')"],
            )

        self.assertEqual(exit_code, 1)
        persisted, _ = load_task_record(self.repo_root, self.config.task_dir, task["id"])
        gate_codes = {gate["code"] for gate in persisted["gates"]}
        self.assertIn("SPEC_FREEZE_REQUIRED", gate_codes)

    def test_build_codex_prompt_projects_expected_task_fields(self) -> None:
        prompt = build_codex_prompt(
            repo_root=self.repo_root,
            config=self.config,
            task_id=self.task["id"],
            extra_instruction="focus on the task docs",
        )
        brief_path = self.task["task_dir"].replace("\\", "/") + "/BRIEF.md"

        self.assertEqual(prompt.task_id, self.task["id"])
        self.assertIn('"id":', prompt.prompt)
        self.assertIn('"test_strategy":', prompt.prompt)
        self.assertIn('"design":', prompt.prompt)
        self.assertIn("Additional operator instruction: focus on the task docs", prompt.prompt)
        self.assertIn("STATUS: completed", prompt.prompt)
        self.assertIn("## Sisyphus Operating Principles", prompt.prompt)
        self.assertIn("## Execution Contract", prompt.prompt)
        self.assertIn("Break it: identify the assumption most likely to fail", prompt.prompt)
        self.assertIn("Change the system, not only the explanation.", prompt.prompt)
        self.assertIn(f"## BRIEF ({brief_path})", prompt.prompt)

    def test_status_json_includes_conformance_summary(self) -> None:
        task_file = self.repo_root / self.task["task_dir"] / "task.json"
        persisted = json.loads(task_file.read_text(encoding="utf-8"))
        persisted["subtasks"] = [
            {
                "id": "subtask-001",
                "title": "Happy path works",
                "category": "normal",
                "status": "queued",
                "conformance": {
                    "status": "yellow",
                    "last_spec_anchor_at": "2026-04-13T10:00:00Z",
                    "last_checkpoint_type": "pre_exec",
                    "drift_count": 1,
                    "summary": "missing verification mapping",
                },
            }
        ]
        persisted["conformance"] = {
            "status": "yellow",
            "last_spec_anchor_at": "2026-04-13T09:59:00Z",
            "last_checkpoint_type": "post_exec",
            "drift_count": 1,
            "summary": "task has unresolved warning",
        }
        task_file.write_text(json.dumps(persisted, indent=2) + "\n", encoding="utf-8")

        with mock.patch("sisyphus.cli.Path.cwd", return_value=self.repo_root):
            buffer = io.StringIO()
            with redirect_stdout(buffer):
                exit_code = handle_status(
                    as_json=True,
                    only_open=False,
                    only_blocked=False,
                    show_agents=False,
                    stale_after_seconds=900,
                )

        self.assertEqual(exit_code, 0)
        payload = json.loads(buffer.getvalue())
        self.assertEqual(payload[0]["conformance_summary"]["status"], "yellow")
        self.assertEqual(payload[0]["subtasks"][0]["conformance_summary"]["status"], "yellow")

    def test_codex_wrapper_builds_default_codex_exec_command(self) -> None:
        (self.repo_root / ".venv" / "Scripts").mkdir(parents=True, exist_ok=True)
        with mock.patch("sisyphus.provider_wrapper.Path.cwd", return_value=self.repo_root):
            with mock.patch("sisyphus.provider_wrapper._resolve_codex_executable", return_value="codex.cmd"):
                with mock.patch("sisyphus.cli.handle_agent_run", return_value=0) as mocked_run:
                    exit_code = run_provider_wrapper(
                        "codex",
                        [self.task["id"], "worker-codex"],
                    )

        self.assertEqual(exit_code, 0)
        kwargs = mocked_run.call_args.kwargs
        expected_repo_root = str(self.repo_root.resolve())
        self.assertEqual(kwargs["provider"], "codex")
        self.assertEqual(kwargs["command"][:7], ["codex.cmd", "exec", "--full-auto", "--sandbox", "workspace-write", "--output-last-message", kwargs["command"][6]])
        self.assertEqual(kwargs["command"][7:9], ["-C", expected_repo_root])
        self.assertEqual(kwargs["command"][-1], "-")
        self.assertIn("You are the local Codex worker for this task.", kwargs["stdin_text"])
        self.assertEqual(kwargs["env"]["GIT_CONFIG_KEY_0"], "safe.directory")
        self.assertEqual(kwargs["env"]["GIT_CONFIG_VALUE_0"], expected_repo_root)

    def test_codex_wrapper_with_options_still_builds_default_launch(self) -> None:
        with mock.patch("sisyphus.provider_wrapper.Path.cwd", return_value=self.repo_root):
            with mock.patch("sisyphus.provider_wrapper._resolve_codex_executable", return_value="codex.cmd"):
                with mock.patch("sisyphus.cli.handle_agent_run", return_value=0) as mocked_run:
                    exit_code = run_provider_wrapper(
                        "codex",
                        [
                            self.task["id"],
                            "worker-codex",
                            "--role",
                            "worker",
                            "--instruction",
                            "focus on the first subtask",
                        ],
                    )

        self.assertEqual(exit_code, 0)
        kwargs = mocked_run.call_args.kwargs
        expected_repo_root = str(self.repo_root.resolve())
        self.assertEqual(kwargs["role"], "worker")
        self.assertEqual(kwargs["command"][:5], ["codex.cmd", "exec", "--full-auto", "--sandbox", "workspace-write"])
        self.assertEqual(kwargs["command"][-1], "-")
        self.assertIn("Additional operator instruction: focus on the first subtask", kwargs["stdin_text"])
        self.assertEqual(kwargs["env"]["GIT_CONFIG_VALUE_0"], expected_repo_root)

    def test_codex_wrapper_converts_blocked_last_message_into_failure(self) -> None:
        def fake_handle_agent_run(**kwargs):
            output_path = Path(kwargs["command"][kwargs["command"].index("--output-last-message") + 1])
            output_path.write_text("STATUS: blocked\nworkspace is read-only\n", encoding="utf-8")
            return 0

        with mock.patch("sisyphus.provider_wrapper.Path.cwd", return_value=self.repo_root):
            with mock.patch("sisyphus.provider_wrapper._resolve_codex_executable", return_value="codex.cmd"):
                with mock.patch("sisyphus.cli.handle_agent_run", side_effect=fake_handle_agent_run):
                    with mock.patch("sisyphus.provider_wrapper.update_agent") as mocked_update:
                        exit_code = run_provider_wrapper(
                            "codex",
                            [self.task["id"], "worker-blocked-result"],
                        )

        self.assertEqual(exit_code, 1)
        mocked_update.assert_called_once()
        self.assertEqual(mocked_update.call_args.kwargs["status"], "failed")
        self.assertIn("blocked", mocked_update.call_args.kwargs["error"])

    def test_codex_wrapper_conversation_mode_creates_task_and_waits_for_plan_approval(self) -> None:
        subprocess.run(["git", "init", "-b", "main"], cwd=self.repo_root, check=True, capture_output=True, text=True)
        subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=self.repo_root, check=True, capture_output=True, text=True)
        subprocess.run(["git", "config", "user.name", "Test User"], cwd=self.repo_root, check=True, capture_output=True, text=True)
        subprocess.run(["git", "add", "."], cwd=self.repo_root, check=True, capture_output=True, text=True)
        subprocess.run(["git", "commit", "-m", "initial"], cwd=self.repo_root, check=True, capture_output=True, text=True)

        buffer = io.StringIO()
        with mock.patch("sisyphus.provider_wrapper.Path.cwd", return_value=self.repo_root):
            with mock.patch("sisyphus.daemon.run_provider_wrapper", return_value=0) as mocked_nested_run:
                with redirect_stdout(buffer):
                    exit_code = run_provider_wrapper(
                        "codex",
                        [
                            "conversation",
                            "대화로 task를 바로 만들고 codex를 실행해줘",
                            "--title",
                            "Auto create task",
                            "--agent-id",
                            "worker-auto",
                            "--instruction",
                            "focus on setup",
                        ],
                    )

        rendered = buffer.getvalue()
        self.assertEqual(exit_code, 0)
        self.assertIn("created TF-", rendered)
        self.assertNotIn("agent_id: worker-auto", rendered)
        processed_files = list(inbox_processed_dir(self.repo_root).glob("*.json"))
        self.assertEqual(len(processed_files), 1)
        persisted = json.loads(processed_files[0].read_text(encoding="utf-8"))
        self.assertEqual(persisted["status"], "processed")
        self.assertEqual(persisted["result"]["agent_id"], None)
        self.assertFalse(persisted["result"]["auto_run"])
        self.assertIn("plan", persisted["result"]["blocked_reason"])
        self.assertFalse(mocked_nested_run.called)

    def test_agent_run_marks_failed_when_command_cannot_start(self) -> None:
        with mock.patch("sisyphus.cli.Path.cwd", return_value=self.repo_root):
            exit_code = handle_agent_run(
                task_id=self.task["id"],
                agent_id="worker-missing-binary",
                role="worker",
                provider="codex",
                step=None,
                summary=None,
                owned_paths=None,
                heartbeat_seconds=1,
                command=["definitely-missing-binary-do-not-create.exe"],
            )

        agents = list_agents(
            repo_root=self.repo_root,
            config=self.config,
            task_id=self.task["id"],
        )
        failed = next(agent for agent in agents if agent["agent_id"] == "worker-missing-binary")
        self.assertEqual(exit_code, 1)
        self.assertEqual(failed["status"], "failed")
        self.assertTrue(failed["error"])

    def test_agent_run_uses_utf8_for_subprocess_io(self) -> None:
        process = mock.Mock()
        process.pid = 4242
        process.stdout = io.StringIO("ok\n")
        process.stdin = io.StringIO()
        process.wait.return_value = 0

        with mock.patch("sisyphus.cli.detect_repo_root", return_value=self.repo_root):
            with mock.patch("sisyphus.agent_runtime.subprocess.Popen", return_value=process) as mocked_popen:
                exit_code = handle_agent_run(
                    task_id=self.task["id"],
                    agent_id="worker-utf8",
                    role="worker",
                    provider="codex",
                    step="running utf8 worker",
                    summary="spawned by wrapper",
                    owned_paths=None,
                    heartbeat_seconds=1,
                    command=[sys.executable, "-c", "print('ok')"],
                    stdin_text="한글 prompt",
                    env={"FOO": "bar"},
                )

        self.assertEqual(exit_code, 0)
        self.assertEqual(mocked_popen.call_args.kwargs["encoding"], "utf-8")
        self.assertEqual(mocked_popen.call_args.kwargs["errors"], "replace")
        self.assertEqual(mocked_popen.call_args.kwargs["env"]["FOO"], "bar")


class SisyphusDaemonTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.repo_root = Path(self.tempdir.name) / "repo"
        self.repo_root.mkdir(parents=True, exist_ok=True)
        (self.repo_root / ".taskflow.toml").write_text(
            "\n".join(
                [
                    'base_branch = "main"',
                    'worktree_root = "../_worktrees"',
                    'task_dir = ".planning/tasks"',
                    'branch_prefix_feature = "feat"',
                    'branch_prefix_issue = "fix"',
                    "",
                    "[verify]",
                    'default = []',
                    "",
                ]
            ),
            encoding="utf-8",
        )
        (self.repo_root / "README.md").write_text("# daemon repo\n", encoding="utf-8")
        self._init_git_repo(self.repo_root, initial_branch="main")
        self.config = load_config(self.repo_root)

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def _fake_workflow_wrapper(self, provider: str, argv: list[str], *, repo_root: Path | None = None) -> int:
        task_id = argv[0]
        role = argv[argv.index("--role") + 1]
        task, _ = load_task_record(self.repo_root, self.config.task_dir, task_id)
        task_dir = self.repo_root / task["task_dir"]
        if role == "planner":
            (task_dir / "BRIEF.md").write_text(
                "\n".join(
                    [
                        "# Brief",
                        "",
                        "## Task",
                        "",
                        f"- Task ID: `{task_id}`",
                        "",
                        "## Problem",
                        "",
                        "- Need orchestration.",
                        "",
                        "## Desired Outcome",
                        "",
                        "- Workflow completes automatically.",
                        "",
                        "## Acceptance Criteria",
                        "",
                        "- [x] Task reaches a reviewed plan",
                        "- [x] Spec can be frozen",
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
                        "1. Review the task.",
                        "",
                        "## Risks",
                        "",
                        "- Small risk.",
                        "",
                        "## Test Strategy",
                        "",
                        "### Normal Cases",
                        "",
                        "- [x] Requested conversation workflow succeeds",
                        "",
                        "### Edge Cases",
                        "",
                        "- [x] Minimal valid input still behaves predictably",
                        "",
                        "### Exception Cases",
                        "",
                        "- [x] Unexpected failure surfaces an actionable error",
                        "",
                        "## Verification Mapping",
                        "",
                        "- `Requested conversation workflow succeeds` -> `sisyphus verify`",
                        "- `Minimal valid input still behaves predictably` -> `targeted regression test`",
                        "- `Unexpected failure surfaces an actionable error` -> `manual review`",
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
        return 0

    def test_queue_conversation_event_writes_pending_file(self) -> None:
        event, event_path = queue_conversation_event(
            self.repo_root,
            message="대화 요청으로 에이전트 상태 대시보드를 추가해줘",
        )

        self.assertTrue(event_path.exists())
        persisted = json.loads(event_path.read_text(encoding="utf-8"))
        self.assertEqual(persisted["id"], event["id"])
        self.assertEqual(persisted["payload"]["task_type"], "feature")
        self.assertEqual(persisted["payload"]["provider"], "codex")
        self.assertTrue(persisted["payload"]["slug"].startswith("conversation-task-"))

    def test_queue_pull_request_merged_event_writes_pending_file(self) -> None:
        task = create_task_record(
            repo_root=self.repo_root,
            config=self.config,
            task_type="feature",
            slug="merge-receipt",
        )
        materialize_task_templates(task)

        event, event_path = queue_pull_request_merged_event(
            self.repo_root,
            task_id=task["id"],
            branch=task["branch"],
            repo_full_name="jihkang/Sisyphus",
            pr_number=11,
            title="Remove live taskflow compatibility layer",
            base_branch="main",
            head_branch=task["branch"],
            merge_commit_sha="5e0a4b80e9c32f5f52d5fff872eba8ee388ef6ee",
            changed_files=[{"path": "src/sisyphus/cli.py", "status": "modified", "additions": 10, "deletions": 2}],
        )

        self.assertTrue(event_path.exists())
        persisted = json.loads(event_path.read_text(encoding="utf-8"))
        self.assertEqual(persisted["id"], event["id"])
        self.assertEqual(persisted["event_type"], "pull_request_merged")
        self.assertEqual(persisted["payload"]["pr_number"], 11)
        self.assertEqual(persisted["payload"]["task_id"], task["id"])
        self.assertEqual(persisted["payload"]["branch"], task["branch"])
        self.assertEqual(persisted["payload"]["changed_files"][0]["path"], "src/sisyphus/cli.py")

    def test_queue_discord_conversation_stores_source_context(self) -> None:
        context = build_discord_source_context(
            channel_id=12345,
            thread_id=67890,
            message_id=111,
            author_id=222,
            author_name="discord-user",
        )
        event, event_path = queue_discord_conversation(
            self.repo_root,
            message="show agent status in one place",
            channel_id=12345,
            thread_id=67890,
            message_id=111,
            author_id=222,
            author_name="discord-user",
            no_run=True,
        )

        self.assertTrue(event_path.exists())
        persisted = json.loads(event_path.read_text(encoding="utf-8"))
        self.assertEqual(context["kind"], "discord")
        self.assertEqual(event["payload"]["source_context"]["kind"], "discord")
        self.assertEqual(persisted["payload"]["source_context"]["channel_id"], "12345")
        self.assertEqual(persisted["payload"]["source_context"]["thread_id"], "67890")

    def test_queue_conversation_api_returns_structured_result(self) -> None:
        queued = queue_conversation(
            self.repo_root,
            message="show agent status in one place",
            title="Add agent dashboard",
            auto_run=False,
        )

        self.assertTrue(queued.event_path.exists())
        self.assertEqual(queued.event_id, queued.event["id"])
        self.assertEqual(queued.event["payload"]["title"], "Add agent dashboard")

    def test_process_inbox_event_creates_task_and_waits_for_plan_approval(self) -> None:
        _, event_path = queue_conversation_event(
            self.repo_root,
            title="Add agent dashboard",
            message="사용 중인 서브 에이전트들의 상태를 한 눈에 보이게 해줘",
            instruction="focus on status output first",
        )

        with mock.patch("sisyphus.daemon.run_provider_wrapper", return_value=0) as mocked_wrapper:
            event = process_inbox_event(
                repo_root=self.repo_root,
                config=self.config,
                event_path=event_path,
            )

        processed_files = list(inbox_processed_dir(self.repo_root).glob("*.json"))
        self.assertEqual(event["status"], "processed")
        self.assertEqual(len(processed_files), 1)
        persisted = json.loads(processed_files[0].read_text(encoding="utf-8"))
        task_id = persisted["result"]["task_id"]
        task, _ = load_task_record(self.repo_root, self.config.task_dir, task_id)
        task_dir = self.repo_root / task["task_dir"]
        mirrored_task_dir = Path(task["worktree_path"]) / task["task_dir"]

        self.assertTrue((task_dir / "BRIEF.md").exists())
        self.assertTrue((task_dir / "PLAN.md").exists())
        self.assertTrue((mirrored_task_dir / "task.json").exists())
        self.assertTrue((mirrored_task_dir / "BRIEF.md").exists())
        self.assertTrue((mirrored_task_dir / "PLAN.md").exists())
        self.assertIn("Original request:", (task_dir / "BRIEF.md").read_text(encoding="utf-8"))

    def test_process_inbox_event_marks_feature_tasks_promotable_by_default(self) -> None:
        _, event_path = queue_conversation_event(
            self.repo_root,
            title="Add agent dashboard",
            message="show agent status in one place",
            task_type="feature",
            auto_run=False,
        )

        event = process_inbox_event(
            repo_root=self.repo_root,
            config=self.config,
            event_path=event_path,
        )

        self.assertEqual(event["status"], "processed")
        processed_files = list(inbox_processed_dir(self.repo_root).glob("*.json"))
        task_id = json.loads(processed_files[0].read_text(encoding="utf-8"))["result"]["task_id"]
        task, _ = load_task_record(self.repo_root, self.config.task_dir, task_id)

        self.assertTrue(task["promotion"]["required"])
        self.assertEqual(task["promotion"]["status"], "promotion_pending")
        self.assertEqual(task["promotion"]["required_source"], "classified")
        self.assertEqual(task["promotion"]["required_reason"], "feature tasks are promotable by default")

    def test_process_inbox_event_marks_issue_tasks_not_promotable_by_default(self) -> None:
        _, event_path = queue_conversation_event(
            self.repo_root,
            title="Fix agent dashboard",
            message="the dashboard crashes on load",
            task_type="issue",
            auto_run=False,
        )

        event = process_inbox_event(
            repo_root=self.repo_root,
            config=self.config,
            event_path=event_path,
        )

        self.assertEqual(event["status"], "processed")
        processed_files = list(inbox_processed_dir(self.repo_root).glob("*.json"))
        task_id = json.loads(processed_files[0].read_text(encoding="utf-8"))["result"]["task_id"]
        task, _ = load_task_record(self.repo_root, self.config.task_dir, task_id)

        self.assertFalse(task["promotion"]["required"])
        self.assertEqual(task["promotion"]["status"], "not_required")
        self.assertEqual(task["promotion"]["required_source"], "classified")
        self.assertEqual(task["promotion"]["required_reason"], "non-feature tasks are not promotable by default")

    def test_process_inbox_event_skips_promotion_for_test_only_feature_paths(self) -> None:
        _, event_path = queue_conversation_event(
            self.repo_root,
            title="Refine verification artifact",
            message="adjust only the test harness for this feature",
            task_type="feature",
            owned_paths=["tests/test_sisyphus.py"],
            auto_run=False,
        )

        event = process_inbox_event(
            repo_root=self.repo_root,
            config=self.config,
            event_path=event_path,
        )

        self.assertEqual(event["status"], "processed")
        processed_files = list(inbox_processed_dir(self.repo_root).glob("*.json"))
        task_id = json.loads(processed_files[0].read_text(encoding="utf-8"))["result"]["task_id"]
        task, _ = load_task_record(self.repo_root, self.config.task_dir, task_id)

        self.assertEqual(task["meta"]["owned_paths"], ["tests/test_sisyphus.py"])
        self.assertFalse(task["promotion"]["required"])
        self.assertEqual(task["promotion"]["status"], "not_required")
        self.assertEqual(task["promotion"]["required_source"], "classified")
        self.assertEqual(
            task["promotion"]["required_reason"],
            "task only targets tests or internal planning artifacts",
        )

    def test_promotion_required_override_beats_auto_classification(self) -> None:
        _, event_path = queue_conversation_event(
            self.repo_root,
            title="Add agent dashboard",
            message="show agent status in one place",
            task_type="feature",
            auto_run=False,
        )

        event = process_inbox_event(
            repo_root=self.repo_root,
            config=self.config,
            event_path=event_path,
        )

        self.assertEqual(event["status"], "processed")
        processed_files = list(inbox_processed_dir(self.repo_root).glob("*.json"))
        task_id = json.loads(processed_files[0].read_text(encoding="utf-8"))["result"]["task_id"]
        task, task_file = load_task_record(self.repo_root, self.config.task_dir, task_id)
        task["promotion"]["required_override"] = False
        save_task_record(task_file=task_file, task=task)

        reloaded, _ = load_task_record(self.repo_root, self.config.task_dir, task_id)
        self.assertFalse(reloaded["promotion"]["required"])
        self.assertEqual(reloaded["promotion"]["status"], "not_required")
        self.assertEqual(reloaded["promotion"]["required_source"], "override")
        self.assertEqual(
            reloaded["promotion"]["required_reason"],
            "promotion requirement was overridden explicitly",
        )

    def test_process_inbox_event_records_merge_receipt_and_changeset(self) -> None:
        task = create_task_record(
            repo_root=self.repo_root,
            config=self.config,
            task_type="feature",
            slug="merge-receipt-recording",
        )
        materialize_task_templates(task)

        _, event_path = queue_pull_request_merged_event(
            self.repo_root,
            task_id=task["id"],
            branch=task["branch"],
            repo_full_name="jihkang/Sisyphus",
            pr_number=11,
            title="Remove live taskflow compatibility layer",
            url="https://github.com/jihkang/Sisyphus/pull/11",
            base_branch="main",
            head_branch=task["branch"],
            merge_commit_sha="5e0a4b80e9c32f5f52d5fff872eba8ee388ef6ee",
            merged_at="2026-04-18T11:48:11Z",
            additions=12,
            deletions=5,
            changed_files=[
                {"path": "src/sisyphus/cli.py", "status": "modified", "additions": 10, "deletions": 2},
                {
                    "path": "tests/test_sisyphus.py",
                    "status": "renamed",
                    "previous_path": "tests/test_taskflow.py",
                    "additions": 2,
                    "deletions": 3,
                },
            ],
        )

        event = process_inbox_event(
            repo_root=self.repo_root,
            config=self.config,
            event_path=event_path,
        )

        self.assertEqual(event["status"], "processed")
        processed_files = list(inbox_processed_dir(self.repo_root).glob("*.json"))
        self.assertEqual(len(processed_files), 1)
        persisted_event = json.loads(processed_files[0].read_text(encoding="utf-8"))
        self.assertEqual(persisted_event["result"]["pr_number"], 11)
        self.assertFalse(persisted_event["result"]["close_attempted"])
        self.assertFalse(persisted_event["result"]["closed"])
        reloaded, _ = load_task_record(self.repo_root, self.config.task_dir, task["id"])
        promotion_bundle = reloaded["promotion"]
        self.assertTrue(promotion_bundle["required"])
        self.assertEqual(promotion_bundle["status"], "promotion_recorded")
        self.assertEqual(promotion_bundle["pr_number"], 11)
        self.assertEqual(promotion_bundle["pr_url"], "https://github.com/jihkang/Sisyphus/pull/11")
        self.assertEqual(
            promotion_bundle["merge_commit_sha"],
            "5e0a4b80e9c32f5f52d5fff872eba8ee388ef6ee",
        )
        promotion = reloaded["meta"]["promotion"]
        self.assertEqual(promotion["status"], "merged")
        self.assertEqual(promotion["pr_number"], 11)
        self.assertEqual(promotion["merge_commit_sha"], "5e0a4b80e9c32f5f52d5fff872eba8ee388ef6ee")

        task_dir = self.repo_root / task["task_dir"]
        receipt_path = task_dir / "artifacts" / "promotion" / "merge_receipt.json"
        changeset_path = task_dir / "CHANGESET.md"
        self.assertTrue(receipt_path.exists())
        self.assertTrue(changeset_path.exists())
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        self.assertEqual(receipt["pull_request"]["number"], 11)
        self.assertEqual(receipt["changes"]["file_count"], 2)
        changeset = changeset_path.read_text(encoding="utf-8")
        self.assertIn("Pull Request: [#11]", changeset)
        self.assertIn("`src/sisyphus/cli.py`", changeset)
        self.assertIn("`tests/test_sisyphus.py`", changeset)
        self.assertIn("`src`: 1 files", changeset)

    def test_process_inbox_event_records_merge_receipt_and_closes_verified_task(self) -> None:
        task = create_task_record(
            repo_root=self.repo_root,
            config=self.config,
            task_type="feature",
            slug="merge-receipt-close",
        )
        materialize_task_templates(task)
        task_file = self.repo_root / task["task_dir"] / "task.json"
        persisted = json.loads(task_file.read_text(encoding="utf-8"))
        persisted["status"] = "verified"
        persisted["stage"] = "promotion"
        persisted["workflow_phase"] = "promotion_pending"
        persisted["verify_status"] = "passed"
        persisted["plan_status"] = "approved"
        persisted["spec_status"] = "frozen"
        persisted["promotion"] = {
            "required": True,
            "status": "promotion_pending",
            "strategy": "direct",
            "receipt_path": persisted["docs"]["promotion"],
        }
        task_file.write_text(json.dumps(persisted, indent=2) + "\n", encoding="utf-8")

        _, event_path = queue_pull_request_merged_event(
            self.repo_root,
            task_id=task["id"],
            branch=task["branch"],
            repo_full_name="jihkang/Sisyphus",
            pr_number=12,
            title="Close after merge receipt",
            url="https://github.com/jihkang/Sisyphus/pull/12",
            base_branch="main",
            head_branch=task["branch"],
        )

        event = process_inbox_event(
            repo_root=self.repo_root,
            config=self.config,
            event_path=event_path,
        )

        self.assertEqual(event["status"], "processed")
        processed_files = list(inbox_processed_dir(self.repo_root).glob("*.json"))
        persisted_event = json.loads(processed_files[0].read_text(encoding="utf-8"))
        self.assertTrue(persisted_event["result"]["close_attempted"])
        self.assertTrue(persisted_event["result"]["closed"])
        self.assertEqual(persisted_event["result"]["close_status"], "closed")
        self.assertEqual(persisted_event["result"]["close_gate_codes"], [])

        reloaded, _ = load_task_record(self.repo_root, self.config.task_dir, task["id"])
        self.assertEqual(reloaded["promotion"]["status"], "promotion_recorded")
        self.assertEqual(reloaded["status"], "closed")
        self.assertEqual(reloaded["workflow_phase"], "closed")

    def test_record_merged_pull_request_api_returns_structured_result(self) -> None:
        task = create_task_record(
            repo_root=self.repo_root,
            config=self.config,
            task_type="feature",
            slug="merge-receipt-api",
        )
        materialize_task_templates(task)

        result = record_merged_pull_request(
            repo_root=self.repo_root,
            config=self.config,
            task_id=task["id"],
            branch=task["branch"],
            repo_full_name="jihkang/Sisyphus",
            pr_number=11,
            title="Remove live taskflow compatibility layer",
            changed_files=[{"path": "src/sisyphus/cli.py", "status": "modified"}],
        )

        self.assertTrue(result.ok)
        self.assertEqual(result.event_status, "processed")
        self.assertEqual(result.task_id, task["id"])
        self.assertEqual(result.pr_number, 11)
        self.assertIsNotNone(result.receipt_path)
        self.assertIsNotNone(result.changeset_path)
        self.assertFalse(result.close_attempted)
        self.assertFalse(result.closed)

    def test_record_merged_pull_request_api_closes_verified_task_waiting_on_promotion(self) -> None:
        task = create_task_record(
            repo_root=self.repo_root,
            config=self.config,
            task_type="feature",
            slug="merge-receipt-api-close",
        )
        materialize_task_templates(task)
        task_file = self.repo_root / task["task_dir"] / "task.json"
        persisted = json.loads(task_file.read_text(encoding="utf-8"))
        persisted["status"] = "verified"
        persisted["stage"] = "promotion"
        persisted["workflow_phase"] = "promotion_pending"
        persisted["verify_status"] = "passed"
        persisted["plan_status"] = "approved"
        persisted["spec_status"] = "frozen"
        persisted["promotion"] = {
            "required": True,
            "status": "promotion_pending",
            "strategy": "direct",
            "receipt_path": persisted["docs"]["promotion"],
        }
        task_file.write_text(json.dumps(persisted, indent=2) + "\n", encoding="utf-8")

        result = record_merged_pull_request(
            repo_root=self.repo_root,
            config=self.config,
            task_id=task["id"],
            branch=task["branch"],
            repo_full_name="jihkang/Sisyphus",
            pr_number=19,
            title="Close after merge receipt via API",
            changed_files=[{"path": "src/sisyphus/cli.py", "status": "modified"}],
        )

        self.assertTrue(result.ok)
        self.assertTrue(result.close_attempted)
        self.assertTrue(result.closed)
        self.assertEqual(result.close_status, "closed")
        self.assertEqual(result.close_gate_codes, [])

        reloaded, _ = load_task_record(self.repo_root, self.config.task_dir, task["id"])
        self.assertEqual(reloaded["status"], "closed")
        self.assertEqual(reloaded["workflow_phase"], "closed")

    def test_record_merged_pull_request_marks_stacked_child_for_retarget_and_reverify(self) -> None:
        parent = create_task_workspace(
            repo_root=self.repo_root,
            config=self.config,
            task_type="feature",
            slug="retarget-parent",
        ).task
        child = create_task_workspace(
            repo_root=self.repo_root,
            config=self.config,
            task_type="feature",
            slug="retarget-child",
        ).task

        child_file = self.repo_root / child["task_dir"] / "task.json"
        persisted_child = json.loads(child_file.read_text(encoding="utf-8"))
        persisted_child["verify_status"] = "passed"
        persisted_child["status"] = "verified"
        persisted_child["workflow_phase"] = "promotion_pending"
        persisted_child["promotion"] = {
            "required": True,
            "status": "pr_open",
            "strategy": "stacked",
            "parent_task_id": parent["id"],
            "base_branch": parent["branch"],
            "head_branch": child["branch"],
            "pr_number": 88,
            "pr_url": "https://github.com/jihkang/Sisyphus/pull/88",
            "receipt_path": persisted_child["docs"]["promotion"],
        }
        child_file.write_text(json.dumps(persisted_child, indent=2) + "\n", encoding="utf-8")

        result = record_merged_pull_request(
            repo_root=self.repo_root,
            config=self.config,
            task_id=parent["id"],
            branch=parent["branch"],
            repo_full_name="jihkang/Sisyphus",
            pr_number=24,
            title="Merge parent task",
            changed_files=[{"path": "src/sisyphus/promotion.py", "status": "modified"}],
        )

        self.assertTrue(result.ok)
        self.assertEqual(result.child_retargeted_task_ids, [child["id"]])

        reloaded_child, _ = load_task_record(self.repo_root, self.config.task_dir, child["id"])
        self.assertTrue(reloaded_child["promotion"]["retarget_required"])
        self.assertTrue(reloaded_child["promotion"]["reverify_required"])
        self.assertEqual(reloaded_child["promotion"]["retarget_parent_task_id"], parent["id"])
        self.assertEqual(reloaded_child["promotion"]["retarget_parent_branch"], parent["branch"])
        self.assertEqual(reloaded_child["verify_status"], "not_run")
        self.assertEqual(reloaded_child["status"], "blocked")
        self.assertEqual(reloaded_child["workflow_phase"], "retarget_required")
        gate_codes = {gate["code"] for gate in reloaded_child["gates"]}
        self.assertIn("PARENT_RETARGET_REQUIRED", gate_codes)
        event_entries = [
            json.loads(line)
            for line in event_log_file(self.repo_root).read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        self.assertTrue(
            any(
                entry.get("event_type") == "task.manual_intervention_required" and
                entry.get("data", {}).get("task_id") == child["id"] and
                entry.get("data", {}).get("reason") == "parent_retarget_required"
                for entry in event_entries
            )
        )
        self.assertTrue(
            any(
                entry.get("event_type") == "task.reopened_after_verify" and
                entry.get("data", {}).get("task_id") == child["id"]
                for entry in event_entries
            )
        )

    def test_build_value_metrics_report_summarizes_minimum_value_metrics(self) -> None:
        task = create_task_record(
            repo_root=self.repo_root,
            config=self.config,
            task_type="feature",
            slug="value-metrics",
        )
        materialize_task_templates(task)
        task_file = self.repo_root / task["task_dir"] / "task.json"
        persisted = json.loads(task_file.read_text(encoding="utf-8"))
        persisted["verify_status"] = "passed"
        persisted["last_verified_at"] = "2026-04-21T00:01:00Z"
        persisted["promotion"] = {
            "required": True,
            "status": "recorded",
            "strategy": "direct",
            "recorded_at": "2026-04-21T00:06:00Z",
            "receipt_path": persisted["docs"]["promotion"],
        }
        task_file.write_text(json.dumps(persisted, indent=2) + "\n", encoding="utf-8")

        event_log_file(self.repo_root).write_text(
            "\n".join(
                [
                    json.dumps(
                        {
                            "event_id": "evt-session-1",
                            "event_type": "conversation",
                            "status": "queued",
                            "timestamp": "2026-04-21T00:00:00Z",
                        }
                    ),
                    json.dumps(
                        {
                            "event_id": "evt-session-1",
                            "event_type": "conversation",
                            "status": "processed",
                            "timestamp": "2026-04-21T00:00:12Z",
                        }
                    ),
                    new_event_envelope(
                        "verify.completed",
                        data={"task_id": task["id"], "status": "passed"},
                        timestamp="2026-04-21T00:01:00Z",
                    ).to_json(),
                    new_event_envelope(
                        MANUAL_INTERVENTION_REQUIRED_EVENT,
                        data={"task_id": task["id"], "reason": "promotion_required"},
                        timestamp="2026-04-21T00:02:00Z",
                    ).to_json(),
                    new_event_envelope(
                        REOPENED_AFTER_VERIFY_EVENT,
                        data={"task_id": task["id"], "reason": "stacked_parent_merged"},
                        timestamp="2026-04-21T00:07:00Z",
                    ).to_json(),
                ]
            )
            + "\n",
            encoding="utf-8",
        )

        payload = build_value_metrics_report(self.repo_root, self.config)

        self.assertEqual(payload["metrics"]["session_resume_time"]["sample_count"], 1)
        self.assertEqual(payload["metrics"]["session_resume_time"]["summary"]["average_seconds"], 12.0)
        self.assertEqual(payload["metrics"]["reopen_rate_after_verify"]["verified_task_count"], 1)
        self.assertEqual(payload["metrics"]["reopen_rate_after_verify"]["reopened_task_count"], 1)
        self.assertEqual(payload["metrics"]["reopen_rate_after_verify"]["rate"], 1.0)
        self.assertEqual(payload["metrics"]["promotion_lead_time"]["sample_count"], 1)
        self.assertEqual(payload["metrics"]["promotion_lead_time"]["summary"]["average_seconds"], 300.0)
        self.assertEqual(payload["metrics"]["manual_intervention_count"]["count"], 1)
        self.assertEqual(payload["metrics"]["manual_intervention_count"]["by_reason"]["promotion_required"], 1)

    def test_execute_promotion_commits_pushes_and_opens_pull_request(self) -> None:
        self._init_bare_remote(self.repo_root, remote_name="origin")
        outcome = create_task_workspace(
            repo_root=self.repo_root,
            config=self.config,
            task_type="feature",
            slug="promotion-executor",
        )
        task = outcome.task
        task_file = self.repo_root / task["task_dir"] / "task.json"
        persisted = json.loads(task_file.read_text(encoding="utf-8"))
        persisted["promotion"]["required"] = True
        persisted["promotion"]["required_source"] = "override"
        persisted["promotion"]["required_reason"] = "test override"
        task_file.write_text(json.dumps(persisted, indent=2) + "\n", encoding="utf-8")

        worktree = Path(task["worktree_path"])
        (worktree / "README.md").write_text("# daemon repo\npromotion executor\n", encoding="utf-8")

        gh_result = subprocess.CompletedProcess(
            args=["gh", "pr", "create"],
            returncode=0,
            stdout="https://github.com/jihkang/Sisyphus/pull/17\n",
            stderr="",
        )
        with mock.patch("sisyphus.promotion._run_gh", return_value=gh_result) as mocked_gh:
            result = execute_promotion(
                self.repo_root,
                config=self.config,
                task_id=task["id"],
                repo_full_name="jihkang/Sisyphus",
                title="Add promotion executor",
                commit_message="Add promotion executor",
            )

        self.assertTrue(result.ok)
        self.assertEqual(result.status, "pr_open")
        self.assertEqual(result.task_id, task["id"])
        self.assertEqual(result.pr_number, 17)
        self.assertEqual(result.pr_url, "https://github.com/jihkang/Sisyphus/pull/17")
        self.assertIsNotNone(result.receipt_path)
        mocked_gh.assert_called_once()

        reloaded, _ = load_task_record(self.repo_root, self.config.task_dir, task["id"])
        promotion = reloaded["promotion"]
        self.assertEqual(promotion["status"], "pr_open")
        self.assertEqual(promotion["remote_name"], "origin")
        self.assertEqual(promotion["commit_message"], "Add promotion executor")
        self.assertEqual(promotion["pr_number"], 17)
        self.assertEqual(promotion["pr_url"], "https://github.com/jihkang/Sisyphus/pull/17")
        self.assertIsNotNone(promotion["head_sha"])
        self.assertIsNotNone(promotion["execution_receipt_path"])

        receipt_path = self.repo_root / task["task_dir"] / str(promotion["execution_receipt_path"])
        self.assertTrue(receipt_path.exists())
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        self.assertEqual(receipt["status"], "pr_open")
        self.assertEqual(receipt["pull_request"]["number"], 17)
        self.assertEqual(receipt["pull_request"]["url"], "https://github.com/jihkang/Sisyphus/pull/17")

        remote_head = self._run_git(self.repo_root, "ls-remote", "--heads", "origin", task["branch"]).stdout.strip()
        self.assertIn(f"refs/heads/{task['branch']}", remote_head)

    def test_execute_promotion_can_resume_from_pushed_state_without_new_changes(self) -> None:
        self._init_bare_remote(self.repo_root, remote_name="origin")
        outcome = create_task_workspace(
            repo_root=self.repo_root,
            config=self.config,
            task_type="feature",
            slug="promotion-resume",
        )
        task = outcome.task
        task_file = self.repo_root / task["task_dir"] / "task.json"
        persisted = json.loads(task_file.read_text(encoding="utf-8"))
        persisted["promotion"]["required"] = True
        persisted["promotion"]["required_source"] = "override"
        persisted["promotion"]["required_reason"] = "test override"
        task_file.write_text(json.dumps(persisted, indent=2) + "\n", encoding="utf-8")

        worktree = Path(task["worktree_path"])
        (worktree / "README.md").write_text("# daemon repo\nresume promotion\n", encoding="utf-8")
        self._run_git(worktree, "add", "-A")
        self._run_git(worktree, "commit", "-m", "Prepare pushed branch")
        head_sha = self._run_git(worktree, "rev-parse", "HEAD").stdout.strip()
        self._run_git(worktree, "push", "-u", "origin", task["branch"])

        reloaded, _ = load_task_record(self.repo_root, self.config.task_dir, task["id"])
        reloaded["promotion"]["required"] = True
        reloaded["promotion"]["status"] = "pushed"
        reloaded["promotion"]["head_sha"] = head_sha
        reloaded["promotion"]["remote_name"] = "origin"
        task_file.write_text(json.dumps(reloaded, indent=2) + "\n", encoding="utf-8")

        gh_result = subprocess.CompletedProcess(
            args=["gh", "pr", "create"],
            returncode=0,
            stdout="https://github.com/jihkang/Sisyphus/pull/18\n",
            stderr="",
        )
        with mock.patch("sisyphus.promotion._run_gh", return_value=gh_result):
            result = execute_promotion(
                self.repo_root,
                config=self.config,
                task_id=task["id"],
                repo_full_name="jihkang/Sisyphus",
                title="Resume promotion executor",
            )

        self.assertTrue(result.ok)
        self.assertEqual(result.status, "pr_open")
        self.assertEqual(result.commit_sha, head_sha)
        self.assertEqual(result.pr_number, 18)

    def test_execute_promotion_rejects_non_promotable_task(self) -> None:
        self._init_bare_remote(self.repo_root, remote_name="origin")
        outcome = create_task_workspace(
            repo_root=self.repo_root,
            config=self.config,
            task_type="feature",
            slug="promotion-reject",
        )

        result = execute_promotion(
            self.repo_root,
            config=self.config,
            task_id=outcome.task["id"],
            repo_full_name="jihkang/Sisyphus",
        )

        self.assertFalse(result.ok)
        self.assertIn("does not require promotion", result.error or "")

    def test_execute_promotion_uses_parent_branch_for_stacked_base_resolution(self) -> None:
        self._init_bare_remote(self.repo_root, remote_name="origin")
        parent = create_task_workspace(
            repo_root=self.repo_root,
            config=self.config,
            task_type="feature",
            slug="stacked-parent-open",
        ).task
        child = create_task_workspace(
            repo_root=self.repo_root,
            config=self.config,
            task_type="feature",
            slug="stacked-child-open",
        ).task
        child_file = self.repo_root / child["task_dir"] / "task.json"
        persisted = json.loads(child_file.read_text(encoding="utf-8"))
        persisted["promotion"]["required"] = True
        persisted["promotion"]["strategy"] = "stacked"
        persisted["promotion"]["parent_task_id"] = parent["id"]
        child_file.write_text(json.dumps(persisted, indent=2) + "\n", encoding="utf-8")

        child_worktree = Path(child["worktree_path"])
        (child_worktree / "README.md").write_text("# daemon repo\nstacked child open\n", encoding="utf-8")

        gh_result = subprocess.CompletedProcess(
            args=["gh", "pr", "create"],
            returncode=0,
            stdout="https://github.com/jihkang/Sisyphus/pull/21\n",
            stderr="",
        )
        with mock.patch("sisyphus.promotion._run_gh", return_value=gh_result) as mocked_gh:
            result = execute_promotion(
                self.repo_root,
                config=self.config,
                task_id=child["id"],
                repo_full_name="jihkang/Sisyphus",
            )

        self.assertTrue(result.ok)
        self.assertEqual(result.base_branch, parent["branch"])
        gh_args = mocked_gh.call_args.args[1]
        self.assertEqual(gh_args[gh_args.index("--base") + 1], parent["branch"])

        reloaded, _ = load_task_record(self.repo_root, self.config.task_dir, child["id"])
        self.assertEqual(reloaded["promotion"]["base_source"], "parent_task_branch")
        self.assertEqual(reloaded["promotion"]["resolved_parent_branch"], parent["branch"])
        self.assertIn(parent["id"], reloaded["promotion"]["base_reason"])

        receipt_path = self.repo_root / child["task_dir"] / str(reloaded["promotion"]["execution_receipt_path"])
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        self.assertEqual(receipt["base_resolution"]["source"], "parent_task_branch")
        self.assertEqual(receipt["base_resolution"]["parent_task_id"], parent["id"])
        self.assertEqual(receipt["base_resolution"]["parent_branch"], parent["branch"])

    def test_execute_promotion_uses_parent_merge_target_when_parent_is_recorded(self) -> None:
        self._init_bare_remote(self.repo_root, remote_name="origin")
        parent = create_task_workspace(
            repo_root=self.repo_root,
            config=self.config,
            task_type="feature",
            slug="stacked-parent-recorded",
        ).task
        child = create_task_workspace(
            repo_root=self.repo_root,
            config=self.config,
            task_type="feature",
            slug="stacked-child-recorded",
        ).task

        parent_file = self.repo_root / parent["task_dir"] / "task.json"
        persisted_parent = json.loads(parent_file.read_text(encoding="utf-8"))
        persisted_parent["promotion"] = {
            "required": True,
            "status": "promotion_recorded",
            "strategy": "direct",
            "base_branch": "main",
            "head_branch": parent["branch"],
            "receipt_path": persisted_parent["docs"]["promotion"],
        }
        parent_file.write_text(json.dumps(persisted_parent, indent=2) + "\n", encoding="utf-8")

        child_file = self.repo_root / child["task_dir"] / "task.json"
        persisted_child = json.loads(child_file.read_text(encoding="utf-8"))
        persisted_child["promotion"]["required"] = True
        persisted_child["promotion"]["strategy"] = "stacked"
        persisted_child["promotion"]["parent_task_id"] = parent["id"]
        child_file.write_text(json.dumps(persisted_child, indent=2) + "\n", encoding="utf-8")

        child_worktree = Path(child["worktree_path"])
        (child_worktree / "README.md").write_text("# daemon repo\nstacked child recorded\n", encoding="utf-8")

        gh_result = subprocess.CompletedProcess(
            args=["gh", "pr", "create"],
            returncode=0,
            stdout="https://github.com/jihkang/Sisyphus/pull/22\n",
            stderr="",
        )
        with mock.patch("sisyphus.promotion._run_gh", return_value=gh_result) as mocked_gh:
            result = execute_promotion(
                self.repo_root,
                config=self.config,
                task_id=child["id"],
                repo_full_name="jihkang/Sisyphus",
            )

        self.assertTrue(result.ok)
        self.assertEqual(result.base_branch, "main")
        gh_args = mocked_gh.call_args.args[1]
        self.assertEqual(gh_args[gh_args.index("--base") + 1], "main")

        reloaded, _ = load_task_record(self.repo_root, self.config.task_dir, child["id"])
        self.assertEqual(reloaded["promotion"]["base_source"], "parent_merge_target")
        self.assertEqual(reloaded["promotion"]["resolved_parent_branch"], parent["branch"])

    def test_execute_promotion_base_override_beats_stacked_parent_resolution(self) -> None:
        self._init_bare_remote(self.repo_root, remote_name="origin")
        parent = create_task_workspace(
            repo_root=self.repo_root,
            config=self.config,
            task_type="feature",
            slug="stacked-parent-override",
        ).task
        child = create_task_workspace(
            repo_root=self.repo_root,
            config=self.config,
            task_type="feature",
            slug="stacked-child-override",
        ).task
        child_file = self.repo_root / child["task_dir"] / "task.json"
        persisted = json.loads(child_file.read_text(encoding="utf-8"))
        persisted["promotion"]["required"] = True
        persisted["promotion"]["strategy"] = "stacked"
        persisted["promotion"]["parent_task_id"] = parent["id"]
        persisted["promotion"]["base_override"] = "release/2026"
        child_file.write_text(json.dumps(persisted, indent=2) + "\n", encoding="utf-8")

        child_worktree = Path(child["worktree_path"])
        (child_worktree / "README.md").write_text("# daemon repo\nstacked child override\n", encoding="utf-8")

        gh_result = subprocess.CompletedProcess(
            args=["gh", "pr", "create"],
            returncode=0,
            stdout="https://github.com/jihkang/Sisyphus/pull/23\n",
            stderr="",
        )
        with mock.patch("sisyphus.promotion._run_gh", return_value=gh_result) as mocked_gh:
            result = execute_promotion(
                self.repo_root,
                config=self.config,
                task_id=child["id"],
                repo_full_name="jihkang/Sisyphus",
            )

        self.assertTrue(result.ok)
        self.assertEqual(result.base_branch, "release/2026")
        gh_args = mocked_gh.call_args.args[1]
        self.assertEqual(gh_args[gh_args.index("--base") + 1], "release/2026")

        reloaded, _ = load_task_record(self.repo_root, self.config.task_dir, child["id"])
        self.assertEqual(reloaded["promotion"]["base_source"], "explicit_override")
        self.assertEqual(reloaded["promotion"]["base_override"], "release/2026")

    def test_process_inbox_event_persists_discord_source_context_to_task(self) -> None:
        _, event_path = queue_discord_conversation(
            self.repo_root,
            message="show agent status in one place",
            channel_id=12345,
            thread_id=67890,
            message_id=111,
            author_id=222,
            author_name="discord-user",
            no_run=True,
        )

        event = process_inbox_event(
            repo_root=self.repo_root,
            config=self.config,
            event_path=event_path,
        )

        self.assertEqual(event["status"], "processed")
        processed_files = list(inbox_processed_dir(self.repo_root).glob("*.json"))
        persisted = json.loads(processed_files[0].read_text(encoding="utf-8"))
        task_id = persisted["result"]["task_id"]
        task, _ = load_task_record(self.repo_root, self.config.task_dir, task_id)
        self.assertEqual(task["meta"]["source_context"]["kind"], "discord")
        self.assertEqual(task["meta"]["source_context"]["channel_id"], "12345")
        self.assertEqual(task["meta"]["source_context"]["thread_id"], "67890")

    def test_process_inbox_event_adopts_requested_current_changes_into_task_worktree(self) -> None:
        (self.repo_root / "README.md").write_text("# changed in root\n", encoding="utf-8")
        notes_path = self.repo_root / "notes.txt"
        notes_path.write_text("root note\n", encoding="utf-8")

        _, event_path = queue_conversation_event(
            self.repo_root,
            title="Adopt current changes",
            message="carry my current edits into the task worktree",
            adopt_current_changes=True,
            adopt_paths=["README.md"],
            auto_run=False,
        )

        event = process_inbox_event(
            repo_root=self.repo_root,
            config=self.config,
            event_path=event_path,
        )

        self.assertEqual(event["status"], "processed")
        processed_files = list(inbox_processed_dir(self.repo_root).glob("*.json"))
        persisted_event = json.loads(processed_files[0].read_text(encoding="utf-8"))
        task_id = persisted_event["result"]["task_id"]
        task, _ = load_task_record(self.repo_root, self.config.task_dir, task_id)
        adopted = task["meta"]["adopted_changes"]
        self.assertEqual(adopted["source_branch"], "main")
        self.assertEqual(adopted["requested_paths"], ["README.md"])
        self.assertEqual(adopted["paths"], ["README.md"])
        self.assertEqual((Path(task["worktree_path"]) / "README.md").read_text(encoding="utf-8"), "# changed in root\n")
        self.assertFalse((Path(task["worktree_path"]) / "notes.txt").exists())
        log_text = (self.repo_root / task["task_dir"] / "LOG.md").read_text(encoding="utf-8")
        self.assertIn("Adopted 1 current changes from branch `main`", log_text)

    def test_request_task_api_returns_structured_task_result(self) -> None:
        result = request_task(
            repo_root=self.repo_root,
            config=self.config,
            message="create the task but stop before execution",
            title="Create queued task only",
            auto_run=False,
        )

        self.assertTrue(result.ok)
        self.assertEqual(result.event_status, "processed")
        self.assertEqual(result.orchestrated, 0)
        self.assertIsNotNone(result.task_id)
        self.assertIsNotNone(result.task)
        self.assertEqual(result.task["status"], "open")
        self.assertEqual(result.task["plan_status"], "pending_review")

    def test_process_inbox_event_creates_followup_task_for_closed_duplicate_slug(self) -> None:
        existing = create_task_record(
            repo_root=self.repo_root,
            config=self.config,
            task_type="feature",
            slug="stt",
        )
        materialize_task_templates(existing)
        existing_file = self.repo_root / existing["task_dir"] / "task.json"
        persisted_existing = json.loads(existing_file.read_text(encoding="utf-8"))
        persisted_existing["status"] = "closed"
        persisted_existing["stage"] = "done"
        persisted_existing["workflow_phase"] = "closed"
        persisted_existing["verify_status"] = "passed"
        persisted_existing["closed_at"] = "2026-04-05T14:59:45Z"
        existing_file.write_text(json.dumps(persisted_existing, indent=2) + "\n", encoding="utf-8")

        _, event_path = queue_conversation_event(
            self.repo_root,
            title="Implement the real STT workflow",
            message="continue the actual implementation work",
            task_type="feature",
            slug="stt",
            auto_run=False,
        )

        event = process_inbox_event(
            repo_root=self.repo_root,
            config=self.config,
            event_path=event_path,
        )

        self.assertEqual(event["status"], "processed")
        processed_files = list(inbox_processed_dir(self.repo_root).glob("*.json"))
        persisted_event = json.loads(processed_files[0].read_text(encoding="utf-8"))
        self.assertEqual(persisted_event["result"]["requested_slug"], "stt")
        self.assertEqual(persisted_event["result"]["slug"], "stt-followup")
        self.assertEqual(persisted_event["result"]["followup_of_task_id"], existing["id"])

        task_id = persisted_event["result"]["task_id"]
        task, _ = load_task_record(self.repo_root, self.config.task_dir, task_id)
        self.assertEqual(task["slug"], "stt-followup")
        self.assertEqual(task["meta"]["requested_slug"], "stt")
        self.assertEqual(task["meta"]["followup_of_task_id"], existing["id"])
        brief = (self.repo_root / task["task_dir"] / "BRIEF.md").read_text(encoding="utf-8")
        self.assertIn("- Requested Slug: `stt`", brief)
        self.assertIn(f"- Follow-up Of: `{existing['id']}`", brief)

    def test_plan_request_changes_and_approve_update_task_state(self) -> None:
        task = create_task_record(
            repo_root=self.repo_root,
            config=self.config,
            task_type="feature",
            slug="plan-review",
        )
        materialize_task_templates(task)

        requested = request_plan_changes(
            repo_root=self.repo_root,
            config=self.config,
            task_id=task["id"],
            reviewer="reviewer-2",
            notes="split the work more clearly",
        )
        self.assertEqual(requested.plan_status, "changes_requested")
        self.assertEqual(requested.task_status, "blocked")

        approved = approve_task_plan(
            repo_root=self.repo_root,
            config=self.config,
            task_id=task["id"],
            reviewer="reviewer-2",
            notes="approved after update",
        )
        self.assertEqual(approved.plan_status, "approved")
        self.assertEqual(approved.task_status, "open")

        persisted, _ = load_task_record(self.repo_root, self.config.task_dir, task["id"])
        self.assertEqual(persisted["plan_status"], "approved")
        self.assertEqual(persisted["gates"], [])

    def test_plan_revise_resubmits_review_loop(self) -> None:
        task = create_task_record(
            repo_root=self.repo_root,
            config=self.config,
            task_type="feature",
            slug="plan-revise",
        )
        materialize_task_templates(task)

        request_plan_changes(
            repo_root=self.repo_root,
            config=self.config,
            task_id=task["id"],
            reviewer="reviewer-2",
            notes="need clearer steps",
        )
        revised = revise_task_plan(
            repo_root=self.repo_root,
            config=self.config,
            task_id=task["id"],
            author="worker-1",
            notes="updated plan structure",
        )

        self.assertEqual(revised.plan_status, "pending_review")
        persisted, _ = load_task_record(self.repo_root, self.config.task_dir, task["id"])
        self.assertEqual(persisted["workflow_phase"], "plan_in_review")
        self.assertEqual(persisted["plan_review_round"], 1)
        self.assertEqual([entry["action"] for entry in persisted["plan_review_history"]], ["request_changes", "revise"])

    def test_spec_freeze_and_subtask_generation_updates_workflow(self) -> None:
        task = create_task_record(
            repo_root=self.repo_root,
            config=self.config,
            task_type="feature",
            slug="subtask-flow",
        )
        materialize_task_templates(task)
        task_dir = self.repo_root / task["task_dir"]
        (task_dir / "PLAN.md").write_text(
            "\n".join(
                [
                    "# Plan",
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

        approve_task_plan(
            repo_root=self.repo_root,
            config=self.config,
            task_id=task["id"],
            reviewer="reviewer-1",
            notes="plan approved",
        )
        freeze = freeze_task_spec(
            repo_root=self.repo_root,
            config=self.config,
            task_id=task["id"],
            reviewer="reviewer-1",
            notes="spec locked",
        )
        with mock.patch("sisyphus.cli.Path.cwd", return_value=self.repo_root):
            exit_code = handle_subtasks_generate(task["id"])

        self.assertEqual(freeze.spec_status, "frozen")
        self.assertEqual(exit_code, 0)
        persisted, _ = load_task_record(self.repo_root, self.config.task_dir, task["id"])
        self.assertEqual(persisted["workflow_phase"], "execution")
        self.assertEqual(len(persisted["subtasks"]), 3)
        self.assertEqual(persisted["subtasks"][0]["title"], "Happy path works")

    def test_spec_freeze_records_design_anchor(self) -> None:
        task = create_task_record(
            repo_root=self.repo_root,
            config=self.config,
            task_type="feature",
            slug="design-anchor",
        )
        materialize_task_templates(task)
        task_dir = self.repo_root / task["task_dir"]
        (task_dir / "PLAN.md").write_text(
            "\n".join(
                [
                    "# Plan",
                    "",
                    "## Implementation Plan",
                    "",
                    "1. Add a design-aware planner.",
                    "",
                    "## Risks",
                    "",
                    "- The anchor may drift from the task plan.",
                    "",
                    "## Design Evaluation",
                    "",
                    "- Design Mode: `light`",
                    "- Decision Reason: `crosses a few modules`",
                    "- Confidence: `medium`",
                    "- Layer Impact: `layer-touching`",
                    "- Layer Decision Reason: `planning and verify now share a design bundle`",
                    "- Required Design Artifacts: `connection_diagram`",
                    "",
                    "## Design Artifacts",
                    "",
                    "- Connection Diagram: `PLAN.md#connection-diagram`",
                    "- Sequence Diagram: `n/a`",
                    "- Boundary Note: `n/a`",
                    "",
                    "## Test Strategy",
                    "",
                    "### Normal Cases",
                    "",
                    "- [x] Planner persists design state",
                    "",
                    "### Edge Cases",
                    "",
                    "- [x] Missing design artifacts are reported",
                    "",
                    "### Exception Cases",
                    "",
                    "- [x] Existing tasks still verify",
                    "",
                    "## Verification Mapping",
                    "",
                    "- `Planner persists design state` -> `unit_test`",
                    "- `Missing design artifacts are reported` -> `integration_test`",
                    "- `Existing tasks still verify` -> `manual_check`",
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

        approve_task_plan(
            repo_root=self.repo_root,
            config=self.config,
            task_id=task["id"],
            reviewer="reviewer-1",
            notes="plan approved",
        )
        freeze_task_spec(
            repo_root=self.repo_root,
            config=self.config,
            task_id=task["id"],
            reviewer="reviewer-1",
            notes="spec locked",
        )

        persisted, _ = load_task_record(self.repo_root, self.config.task_dir, task["id"])
        conformance = summarize_task_conformance(persisted)

        self.assertEqual(persisted["design"]["frozen"]["mode"], "light")
        self.assertEqual(persisted["design"]["frozen"]["required_artifacts"], ["connection_diagram"])
        self.assertEqual(persisted["design"]["frozen"]["artifacts"]["connection_diagram"], "PLAN.md#connection-diagram")
        self.assertIsNotNone(persisted["design"]["frozen"]["frozen_at"])
        self.assertIsNotNone(conformance["last_design_anchor_at"])
        self.assertIn("mode=light", conformance["design_anchor_summary"])

    def test_run_daemon_once_respects_no_run_events(self) -> None:
        with mock.patch("sisyphus.cli.Path.cwd", return_value=self.repo_root):
            exit_code = handle_ingest_conversation(
                message="CLI를 통해 conversation event를 생성해줘",
                title="Create queued task only",
                task_type="feature",
                slug=None,
                instruction=None,
                agent_id="worker-ingest",
                role="worker",
                provider="codex",
                owned_paths=None,
                provider_args=None,
                adopt_current_changes=False,
                adopt_paths=None,
                no_run=True,
            )

        self.assertEqual(exit_code, 0)
        with mock.patch("sisyphus.daemon.run_provider_wrapper", return_value=0) as mocked_wrapper:
            stats = run_daemon(
                repo_root=self.repo_root,
                config=self.config,
                once=True,
                poll_interval_seconds=1,
            )

        self.assertEqual(stats.processed, 1)
        self.assertEqual(stats.failed, 0)
        self.assertFalse(mocked_wrapper.called)
        processed = list(inbox_processed_dir(self.repo_root).glob("*.json"))
        persisted = json.loads(processed[0].read_text(encoding="utf-8"))
        self.assertFalse(persisted["result"]["auto_run"])
        self.assertIsNone(persisted["result"]["agent_id"])

    def test_run_daemon_once_stops_at_pending_review_until_user_approval(self) -> None:
        queue_conversation_event(
            self.repo_root,
            title="Add agent dashboard",
            message="show agent status in one place",
        )

        with mock.patch("sisyphus.workflow.run_provider_wrapper", side_effect=self._fake_workflow_wrapper) as mocked_wrapper:
            stats = run_daemon(
                repo_root=self.repo_root,
                config=self.config,
                once=True,
                poll_interval_seconds=1,
            )

        self.assertEqual(stats.orchestrated, 0)
        self.assertFalse(mocked_wrapper.called)
        processed_files = list(inbox_processed_dir(self.repo_root).glob("*.json"))
        self.assertEqual(len(processed_files), 1)
        persisted_event = json.loads(processed_files[0].read_text(encoding="utf-8"))
        task_id = persisted_event["result"]["task_id"]
        task, _ = load_task_record(self.repo_root, self.config.task_dir, task_id)
        self.assertEqual(task["status"], "blocked")
        self.assertEqual(task["workflow_phase"], "plan_in_review")
        self.assertEqual(task["plan_status"], "pending_review")
        self.assertEqual(task["spec_status"], "draft")
        self.assertEqual(task["subtasks"], [])

    def test_request_command_stops_at_pending_review_until_user_approval(self) -> None:
        buffer = io.StringIO()
        with mock.patch("sisyphus.cli.Path.cwd", return_value=self.repo_root):
            with mock.patch("sisyphus.workflow.run_provider_wrapper", side_effect=self._fake_workflow_wrapper) as mocked_wrapper:
                with redirect_stdout(buffer):
                    exit_code = handle_request(
                        message="show agent status in one place",
                        title="Add agent dashboard",
                        task_type="feature",
                        slug=None,
                        instruction=None,
                        agent_id="worker-1",
                        role="worker",
                        provider="codex",
                        owned_paths=None,
                        provider_args=None,
                        adopt_current_changes=False,
                        adopt_paths=None,
                        no_run=False,
                    )

        self.assertEqual(exit_code, 0)
        self.assertFalse(mocked_wrapper.called)
        rendered = buffer.getvalue()
        self.assertIn("request evt-", rendered)
        self.assertIn("status: blocked", rendered)
        self.assertIn("plan_status: pending_review", rendered)
        self.assertIn("workflow_phase: plan_in_review", rendered)
        processed_files = list(inbox_processed_dir(self.repo_root).glob("*.json"))
        self.assertEqual(len(processed_files), 1)
        persisted_event = json.loads(processed_files[0].read_text(encoding="utf-8"))
        task_id = persisted_event["result"]["task_id"]
        task, _ = load_task_record(self.repo_root, self.config.task_dir, task_id)
        self.assertEqual(task["status"], "blocked")
        self.assertEqual(task["workflow_phase"], "plan_in_review")
        self.assertEqual(task["plan_status"], "pending_review")

    def test_request_command_respects_no_run(self) -> None:
        buffer = io.StringIO()
        with mock.patch("sisyphus.cli.Path.cwd", return_value=self.repo_root):
            with mock.patch("sisyphus.workflow.run_provider_wrapper", side_effect=self._fake_workflow_wrapper) as mocked_wrapper:
                with redirect_stdout(buffer):
                    exit_code = handle_request(
                        message="create the task but stop before execution",
                        title="Create queued task only",
                        task_type="feature",
                        slug=None,
                        instruction=None,
                        agent_id="worker-1",
                        role="worker",
                        provider="codex",
                        owned_paths=None,
                        provider_args=None,
                        adopt_current_changes=False,
                        adopt_paths=None,
                        no_run=True,
                    )

        self.assertEqual(exit_code, 0)
        self.assertFalse(mocked_wrapper.called)
        rendered = buffer.getvalue()
        self.assertIn("status: open", rendered)
        self.assertIn("plan_status: pending_review", rendered)
        self.assertIn("workflow_phase: plan_in_review", rendered)
        processed_files = list(inbox_processed_dir(self.repo_root).glob("*.json"))
        self.assertEqual(len(processed_files), 1)
        persisted_event = json.loads(processed_files[0].read_text(encoding="utf-8"))
        self.assertFalse(persisted_event["result"]["auto_run"])
        task_id = persisted_event["result"]["task_id"]
        task, _ = load_task_record(self.repo_root, self.config.task_dir, task_id)
        self.assertEqual(task["status"], "open")
        self.assertEqual(task["plan_status"], "pending_review")

    def test_request_command_reports_adopted_changes(self) -> None:
        (self.repo_root / "README.md").write_text("# changed in root\n", encoding="utf-8")
        buffer = io.StringIO()

        with mock.patch("sisyphus.cli.Path.cwd", return_value=self.repo_root):
            with redirect_stdout(buffer):
                exit_code = handle_request(
                    message="attach my current edit to the task",
                    title="Adopt local README change",
                    task_type="feature",
                    slug=None,
                    instruction=None,
                    agent_id="worker-1",
                    role="worker",
                    provider="codex",
                    owned_paths=None,
                    provider_args=None,
                    adopt_current_changes=True,
                    adopt_paths=["README.md"],
                    no_run=True,
                )

        self.assertEqual(exit_code, 0)
        rendered = buffer.getvalue()
        self.assertIn("adopted_paths: 1", rendered)
        self.assertIn("adopted_from_branch: main", rendered)

    def test_request_command_prints_followup_context_for_closed_duplicate_slug(self) -> None:
        existing = create_task_record(
            repo_root=self.repo_root,
            config=self.config,
            task_type="feature",
            slug="stt",
        )
        materialize_task_templates(existing)
        existing_file = self.repo_root / existing["task_dir"] / "task.json"
        persisted_existing = json.loads(existing_file.read_text(encoding="utf-8"))
        persisted_existing["status"] = "closed"
        persisted_existing["stage"] = "done"
        persisted_existing["workflow_phase"] = "closed"
        persisted_existing["verify_status"] = "passed"
        persisted_existing["closed_at"] = "2026-04-05T14:59:45Z"
        existing_file.write_text(json.dumps(persisted_existing, indent=2) + "\n", encoding="utf-8")

        buffer = io.StringIO()
        with mock.patch("sisyphus.cli.Path.cwd", return_value=self.repo_root):
            with redirect_stdout(buffer):
                exit_code = handle_request(
                    message="continue the actual implementation work",
                    title="Implement the real STT workflow",
                    task_type="feature",
                    slug="stt",
                    instruction=None,
                    agent_id="worker-1",
                    role="worker",
                    provider="codex",
                    owned_paths=None,
                    provider_args=None,
                    adopt_current_changes=False,
                    adopt_paths=None,
                    no_run=True,
                )

        self.assertEqual(exit_code, 0)
        rendered = buffer.getvalue()
        self.assertIn("slug: stt-followup", rendered)
        self.assertIn("requested_slug: stt", rendered)
        self.assertIn(f"followup_of_task_id: {existing['id']}", rendered)

    def test_request_command_honors_explicit_repo_root(self) -> None:
        outside_root = self.repo_root.parent / "outside"
        outside_root.mkdir(parents=True, exist_ok=True)
        buffer = io.StringIO()

        with mock.patch("sisyphus.cli.Path.cwd", return_value=outside_root):
            with mock.patch("sisyphus.workflow.run_provider_wrapper", side_effect=self._fake_workflow_wrapper):
                with redirect_stdout(buffer):
                    exit_code = handle_request(
                        message="show agent status in one place",
                        title="Add agent dashboard",
                        task_type="feature",
                        slug=None,
                        instruction=None,
                        agent_id="worker-1",
                        role="worker",
                        provider="codex",
                        owned_paths=None,
                        provider_args=None,
                        adopt_current_changes=False,
                        adopt_paths=None,
                        no_run=True,
                        repo_root=self.repo_root,
                    )

        self.assertEqual(exit_code, 0)
        rendered = buffer.getvalue()
        self.assertIn("status: open", rendered)
        self.assertTrue(list(inbox_processed_dir(self.repo_root).glob("*.json")))
        self.assertFalse((outside_root / ".planning").exists())

    def test_run_service_step_emits_notification_for_discord_task(self) -> None:
        queue_discord_conversation(
            self.repo_root,
            message="show agent status in one place",
            channel_id=12345,
            thread_id=67890,
            message_id=111,
            author_id=222,
            author_name="discord-user",
            no_run=True,
        )

        tracker = TaskNotificationTracker()
        result = run_service_step(
            repo_root=self.repo_root,
            config=self.config,
            tracker=tracker,
        )

        self.assertEqual(result.stats.processed, 1)
        self.assertEqual(len(result.notifications), 1)
        notification = result.notifications[0]
        self.assertEqual(notification.source_context["kind"], "discord")
        self.assertEqual(notification.source_context["channel_id"], "12345")
        self.assertIn("phase=plan_in_review", notification.summary)

    def test_build_task_update_summary_includes_subtask_progress(self) -> None:
        task = {
            "id": "TF-20260405-feature-summary",
            "status": "open",
            "workflow_phase": "execution",
            "plan_status": "approved",
            "spec_status": "frozen",
            "subtasks": [
                {"id": "subtask-1", "status": "completed"},
                {"id": "subtask-2", "status": "queued"},
            ],
        }

        summary = build_task_update_summary(task)

        self.assertIn("TF-20260405-feature-summary", summary)
        self.assertIn("subtasks=1/2", summary)

    def test_build_task_update_summary_includes_followup_context(self) -> None:
        task = {
            "id": "TF-20260405-feature-stt-followup",
            "slug": "stt-followup",
            "status": "open",
            "workflow_phase": "plan_in_review",
            "plan_status": "pending_review",
            "spec_status": "draft",
            "subtasks": [],
            "meta": {
                "requested_slug": "stt",
                "followup_of_task_id": "TF-20260405-feature-stt",
            },
        }

        summary = build_task_update_summary(task)

        self.assertIn("requested_slug=stt", summary)
        self.assertIn("followup_of=TF-20260405-feature-stt", summary)

    def test_build_task_update_summary_includes_promotion_status(self) -> None:
        task = {
            "id": "TF-20260405-feature-promotion",
            "status": "open",
            "workflow_phase": "execution",
            "plan_status": "approved",
            "spec_status": "frozen",
            "subtasks": [],
            "promotion": {
                "required": True,
                "status": "pr_open",
                "strategy": "direct",
                "pr_number": 23,
            },
        }

        summary = build_task_update_summary(task)

        self.assertIn("promotion=pr_open#23", summary)

    def test_workflow_cycle_does_not_auto_advance_pending_review_tasks(self) -> None:
        task = create_task_record(
            repo_root=self.repo_root,
            config=self.config,
            task_type="feature",
            slug="review-limit",
        )
        materialize_task_templates(task)
        task_file = self.repo_root / task["task_dir"] / "task.json"
        persisted = json.loads(task_file.read_text(encoding="utf-8"))
        persisted["max_plan_review_rounds"] = 1
        task_file.write_text(json.dumps(persisted, indent=2) + "\n", encoding="utf-8")

        progressed = run_workflow_cycle(repo_root=self.repo_root, config=self.config)

        self.assertEqual(progressed, 0)
        reloaded, _ = load_task_record(self.repo_root, self.config.task_dir, task["id"])
        self.assertEqual(reloaded["workflow_phase"], "plan_in_review")
        self.assertEqual(reloaded["plan_status"], "pending_review")

    def test_workflow_cycle_does_not_auto_advance_promotion_pending_tasks(self) -> None:
        task = create_task_record(
            repo_root=self.repo_root,
            config=self.config,
            task_type="feature",
            slug="promotion-pending-phase",
        )
        materialize_task_templates(task)
        task_file = self.repo_root / task["task_dir"] / "task.json"
        persisted = json.loads(task_file.read_text(encoding="utf-8"))
        persisted["status"] = "verified"
        persisted["stage"] = "promotion"
        persisted["workflow_phase"] = "promotion_pending"
        persisted["verify_status"] = "passed"
        persisted["plan_status"] = "approved"
        persisted["spec_status"] = "frozen"
        persisted.setdefault("meta", {})["auto_loop_enabled"] = True
        persisted["promotion"] = {
            "required": True,
            "status": "promotion_pending",
            "strategy": "direct",
            "receipt_path": persisted["docs"]["promotion"],
        }
        task_file.write_text(json.dumps(persisted, indent=2) + "\n", encoding="utf-8")

        progressed = run_workflow_cycle(repo_root=self.repo_root, config=self.config)

        self.assertEqual(progressed, 0)
        reloaded, _ = load_task_record(self.repo_root, self.config.task_dir, task["id"])
        self.assertEqual(reloaded["workflow_phase"], "promotion_pending")
        self.assertEqual(reloaded["status"], "verified")

    def test_workflow_cycle_does_not_auto_advance_retarget_required_tasks(self) -> None:
        task = create_task_record(
            repo_root=self.repo_root,
            config=self.config,
            task_type="feature",
            slug="retarget-required-phase",
        )
        materialize_task_templates(task)
        task_file = self.repo_root / task["task_dir"] / "task.json"
        persisted = json.loads(task_file.read_text(encoding="utf-8"))
        persisted["status"] = "blocked"
        persisted["stage"] = "promotion"
        persisted["workflow_phase"] = "retarget_required"
        persisted["verify_status"] = "not_run"
        persisted["plan_status"] = "approved"
        persisted["spec_status"] = "frozen"
        persisted.setdefault("meta", {})["auto_loop_enabled"] = True
        persisted["promotion"] = {
            "required": True,
            "status": "pr_open",
            "strategy": "stacked",
            "retarget_required": True,
            "reverify_required": True,
            "receipt_path": persisted["docs"]["promotion"],
        }
        task_file.write_text(json.dumps(persisted, indent=2) + "\n", encoding="utf-8")

        progressed = run_workflow_cycle(repo_root=self.repo_root, config=self.config)

        self.assertEqual(progressed, 0)
        reloaded, _ = load_task_record(self.repo_root, self.config.task_dir, task["id"])
        self.assertEqual(reloaded["workflow_phase"], "retarget_required")
        self.assertEqual(reloaded["status"], "blocked")

    def test_process_inbox_event_moves_failure_to_failed_folder(self) -> None:
        _, event_path = queue_conversation_event(
            self.repo_root,
            title="Broken codex launch",
            message="로컬 codex 실행이 실패하는 경우도 남겨줘",
        )

        with mock.patch("sisyphus.daemon.enforce_plan_approved", side_effect=lambda **kwargs: (True, load_task_record(self.repo_root, self.config.task_dir, kwargs["task_id"])[0])):
            with mock.patch("sisyphus.daemon.enforce_spec_frozen", side_effect=lambda **kwargs: (True, load_task_record(self.repo_root, self.config.task_dir, kwargs["task_id"])[0])):
                with mock.patch("sisyphus.daemon.run_provider_wrapper", return_value=7):
                    event = process_inbox_event(
                        repo_root=self.repo_root,
                        config=self.config,
                        event_path=event_path,
                    )

        failed_files = list(inbox_failed_dir(self.repo_root).glob("*.json"))
        self.assertEqual(event["status"], "failed")
        self.assertEqual(len(failed_files), 1)
        persisted = json.loads(failed_files[0].read_text(encoding="utf-8"))
        self.assertIn("code 7", persisted["error"])

    def test_agent_run_parser_keeps_remainder_command_args(self) -> None:
        parser = build_parser()

        args, extras = parser.parse_known_args(
            [
                "agent",
                "run",
                "TF-20260405-feature-demo",
                "worker-1",
                "--role",
                "worker",
                "--provider",
                "codex",
                "--",
                "python",
                "-c",
                "print('ok')",
            ]
        )

        self.assertEqual(args.command, "agent")
        self.assertEqual(args.agent_command, "run")
        self.assertEqual(extras, ["--", "python", "-c", "print('ok')"])

    def test_parser_uses_sisyphus_as_program_name(self) -> None:
        parser = build_parser()

        self.assertEqual(parser.prog, "sisyphus")
        self.assertIn("usage: sisyphus", parser.format_usage())

    def test_sisyphus_cli_module_reexports_parser_and_main(self) -> None:
        self.assertIs(sisyphus_cli.build_parser, build_parser)
        self.assertIs(sisyphus_cli.main, cli_main)

    def test_request_parser_accepts_conversation_arguments(self) -> None:
        parser = build_parser()

        args = parser.parse_args(
            [
                "request",
                "add agent dashboard",
                "--task-type",
                "feature",
                "--agent-id",
                "worker-1",
                "--provider",
                "codex",
                "--adopt-current-changes",
                "--adopt-path",
                "README.md",
                "--no-run",
            ]
        )

        self.assertEqual(args.command, "request")
        self.assertEqual(args.message, "add agent dashboard")
        self.assertEqual(args.agent_id, "worker-1")
        self.assertTrue(args.adopt_current_changes)
        self.assertEqual(args.adopt_paths, ["README.md"])
        self.assertTrue(args.no_run)

    def test_ingest_pr_merged_parser_accepts_merge_receipt_arguments(self) -> None:
        parser = build_parser()

        args = parser.parse_args(
            [
                "ingest",
                "pr-merged",
                "--task-id",
                "TF-20260418-feature-demo",
                "--pr-number",
                "11",
                "--title",
                "Remove live taskflow compatibility layer",
                "--merge-commit-sha",
                "5e0a4b80e9c32f5f52d5fff872eba8ee388ef6ee",
                "--changed-file-json",
                '{"path":"src/sisyphus/cli.py","status":"modified"}',
            ]
        )

        self.assertEqual(args.command, "ingest")
        self.assertEqual(args.ingest_command, "pr-merged")
        self.assertEqual(args.task_id, "TF-20260418-feature-demo")
        self.assertEqual(args.pr_number, 11)
        self.assertEqual(args.changed_file_json, ['{"path":"src/sisyphus/cli.py","status":"modified"}'])

    def test_parser_accepts_global_repo_override(self) -> None:
        parser = build_parser()

        args = parser.parse_args(
            [
                "--repo",
                str(self.repo_root),
                "request",
                "add agent dashboard",
                "--no-run",
            ]
        )

        self.assertEqual(args.repo_root, str(self.repo_root))
        self.assertEqual(args.command, "request")
        self.assertTrue(args.no_run)

    def test_parser_accepts_serve_and_discord_bot_commands(self) -> None:
        parser = build_parser()

        serve_args = parser.parse_args(["--repo", str(self.repo_root), "serve", "--poll-interval-seconds", "7"])
        discord_args = parser.parse_args(
            [
                "--repo",
                str(self.repo_root),
                "discord-bot",
                "--token",
                "secret",
                "--channel-id",
                "12345",
                "--poll-interval-seconds",
                "9",
            ]
        )

        self.assertEqual(serve_args.command, "serve")
        self.assertEqual(serve_args.repo_root, str(self.repo_root))
        self.assertEqual(serve_args.poll_interval_seconds, 7)
        self.assertEqual(discord_args.command, "discord-bot")
        self.assertEqual(discord_args.repo_root, str(self.repo_root))
        self.assertEqual(discord_args.token, "secret")
        self.assertEqual(discord_args.channel_ids, [12345])
        self.assertEqual(discord_args.poll_interval_seconds, 9)

    def test_parser_accepts_evolution_read_only_surface(self) -> None:
        parser = build_parser()

        run_args = parser.parse_args(["--repo", str(self.repo_root), "evolution", "run", "EVR-demo"])
        status_args = parser.parse_args(["--repo", str(self.repo_root), "evolution", "status", "EVR-demo"])
        report_args = parser.parse_args(["--repo", str(self.repo_root), "evolution", "report", "EVR-demo"])
        compare_args = parser.parse_args(
            [
                "--repo",
                str(self.repo_root),
                "evolution",
                "compare",
                "EVR-left",
                "EVR-right",
            ]
        )

        self.assertEqual(run_args.command, "evolution")
        self.assertEqual(run_args.evolution_command, "run")
        self.assertEqual(run_args.run_id, "EVR-demo")
        self.assertEqual(status_args.evolution_command, "status")
        self.assertEqual(report_args.evolution_command, "report")
        self.assertEqual(compare_args.evolution_command, "compare")
        self.assertEqual(compare_args.left_run_id, "EVR-left")
        self.assertEqual(compare_args.right_run_id, "EVR-right")

    def test_parser_accepts_evolution_execute_surface(self) -> None:
        parser = build_parser()

        execute_args = parser.parse_args(
            [
                "--repo",
                str(self.repo_root),
                "evolution",
                "execute",
                "--run-id",
                "EVR-demo",
                "--target-id",
                "execution-contract-wording",
                "--target-id",
                "mcp-tool-descriptions",
                "--task-id",
                "TF-1",
                "--max-events",
                "7",
            ]
        )

        self.assertEqual(execute_args.command, "evolution")
        self.assertEqual(execute_args.evolution_command, "execute")
        self.assertEqual(execute_args.run_id, "EVR-demo")
        self.assertEqual(execute_args.target_ids, ["execution-contract-wording", "mcp-tool-descriptions"])
        self.assertEqual(execute_args.task_ids, ["TF-1"])
        self.assertEqual(execute_args.max_events, 7)

    def test_parser_accepts_evolution_followup_and_decide_surfaces(self) -> None:
        parser = build_parser()

        followup_args = parser.parse_args(
            [
                "--repo",
                str(self.repo_root),
                "evolution",
                "request-followup",
                "EVR-demo",
                "--candidate-id",
                "candidate-001",
                "--title",
                "Request follow-up",
                "--summary",
                "Create a review-gated task.",
                "--task-type",
                "feature",
                "--target-id",
                "execution-contract-wording",
                "--owned-path",
                "docs/architecture.md",
                "--review-gate",
                "plan_review",
                "--verification-obligation-json",
                '{"claim":"preserves intent","method":"sisyphus verify","required":true}',
                "--evidence-summary-json",
                '{"kind":"report","summary":"from evolution report","locator":"report.md"}',
            ]
        )
        decide_args = parser.parse_args(
            [
                "--repo",
                str(self.repo_root),
                "evolution",
                "decide",
                "TF-123",
                "--claim",
                "candidate remains reviewable",
            ]
        )

        self.assertEqual(followup_args.command, "evolution")
        self.assertEqual(followup_args.evolution_command, "request-followup")
        self.assertEqual(followup_args.run_id, "EVR-demo")
        self.assertEqual(followup_args.candidate_id, "candidate-001")
        self.assertEqual(followup_args.requested_task_type, "feature")
        self.assertEqual(followup_args.target_ids, ["execution-contract-wording"])
        self.assertEqual(followup_args.owned_paths, ["docs/architecture.md"])
        self.assertEqual(followup_args.review_gates, ["plan_review"])
        self.assertEqual(len(followup_args.verification_obligation_json), 1)
        self.assertEqual(len(followup_args.evidence_summary_json), 1)
        self.assertEqual(decide_args.evolution_command, "decide")
        self.assertEqual(decide_args.task_id, "TF-123")
        self.assertEqual(decide_args.claim, "candidate remains reviewable")

    def test_handle_evolution_execute_renders_created_run(self) -> None:
        with mock.patch(
            "sisyphus.cli.execute_evolution_surface",
            return_value=SimpleNamespace(
                ok=True,
                run_id="EVR-demo",
                artifact_dir=str(self.repo_root / ".planning" / "evolution" / "runs" / "EVR-demo"),
                resource_uri="evolution://EVR-demo/run",
                final_stage="report_built",
                content="evolution run EVR-demo\nfinal_stage: report_built\n",
                error=None,
                error_type=None,
                failure_stage=None,
            ),
        ):
            stdout = io.StringIO()
            with redirect_stdout(stdout):
                exit_code = handle_evolution_execute(
                    run_id="EVR-demo",
                    target_ids=["execution-contract-wording"],
                    task_ids=["TF-1"],
                    max_events=5,
                    repo_root=self.repo_root,
                )

        self.assertEqual(exit_code, 0)
        self.assertIn("evolution run EVR-demo", stdout.getvalue())

    def test_handle_evolution_execute_reports_actionable_failure(self) -> None:
        with mock.patch(
            "sisyphus.cli.execute_evolution_surface",
            return_value=SimpleNamespace(
                ok=False,
                run_id="EVR-demo",
                artifact_dir=str(self.repo_root / ".planning" / "evolution" / "runs" / "EVR-demo"),
                resource_uri="evolution://EVR-demo/run",
                final_stage="failed",
                content="evolution execute failed\n",
                error="run already exists",
                error_type="FileExistsError",
                failure_stage=None,
            ),
        ):
            stderr = io.StringIO()
            with redirect_stderr(stderr):
                exit_code = handle_evolution_execute(
                    run_id="EVR-demo",
                    target_ids=None,
                    task_ids=None,
                    max_events=5,
                    repo_root=self.repo_root,
                )

        self.assertEqual(exit_code, 1)
        self.assertIn("error: run already exists", stderr.getvalue())
        self.assertIn("run_id: EVR-demo", stderr.getvalue())
        self.assertIn("error_type: FileExistsError", stderr.getvalue())

    def test_handle_evolution_request_followup_renders_created_task(self) -> None:
        with mock.patch(
            "sisyphus.cli.request_evolution_followup",
            return_value=SimpleNamespace(
                task_id="TF-followup",
                task_uri="task://TF-followup/record",
                run_id="EVR-demo",
                candidate_id="candidate-001",
                requested_targets=("execution-contract-wording",),
                required_review_gates=("plan_review", "verify"),
                content="evolution followup request EVR-demo candidate-001\nfollowup_task_id: TF-followup\n",
            ),
        ):
            stdout = io.StringIO()
            with redirect_stdout(stdout):
                exit_code = handle_evolution_request_followup(
                    run_id="EVR-demo",
                    candidate_id="candidate-001",
                    title="Request follow-up",
                    summary="Create a review-gated task.",
                    requested_task_type="feature",
                    slug="request-followup",
                    target_ids=["execution-contract-wording"],
                    owned_paths=["docs/architecture.md"],
                    review_gates=["plan_review"],
                    verification_obligation_json=[
                        '{"claim":"preserves intent","method":"sisyphus verify","required":true}'
                    ],
                    evidence_summary_json=[
                        '{"kind":"report","summary":"from evolution report","locator":"report.md"}'
                    ],
                    repo_root=self.repo_root,
                )

        self.assertEqual(exit_code, 0)
        self.assertIn("evolution followup request EVR-demo candidate-001", stdout.getvalue())

    def test_handle_evolution_request_followup_reports_bad_json(self) -> None:
        stderr = io.StringIO()
        with redirect_stderr(stderr):
            exit_code = handle_evolution_request_followup(
                run_id="EVR-demo",
                candidate_id="candidate-001",
                title="Request follow-up",
                summary="Create a review-gated task.",
                requested_task_type="feature",
                slug=None,
                target_ids=None,
                owned_paths=None,
                review_gates=None,
                verification_obligation_json=["[]"],
                evidence_summary_json=None,
                repo_root=self.repo_root,
            )

        self.assertEqual(exit_code, 1)
        self.assertIn("verification obligation entry 1 must decode to an object", stderr.getvalue())

    def test_handle_evolution_decide_renders_decision(self) -> None:
        with mock.patch(
            "sisyphus.cli.evaluate_evolution_followup_decision",
            return_value=SimpleNamespace(
                task_id="TF-followup",
                task_uri="task://TF-followup/record",
                run_id="EVR-demo",
                candidate_id="candidate-001",
                gate_status="eligible_for_promotion",
                envelope_status="promotion",
                content="evolution decision TF-followup\ngate_status: eligible_for_promotion\n",
            ),
        ):
            stdout = io.StringIO()
            with redirect_stdout(stdout):
                exit_code = handle_evolution_decide(
                    task_id="TF-followup",
                    claim="candidate remains eligible",
                    repo_root=self.repo_root,
                )

        self.assertEqual(exit_code, 0)
        self.assertIn("eligible_for_promotion", stdout.getvalue())

    def test_handle_evolution_decide_reports_actionable_failure(self) -> None:
        with mock.patch(
            "sisyphus.cli.evaluate_evolution_followup_decision",
            side_effect=ValueError("task is not an evolution follow-up task"),
        ):
            stderr = io.StringIO()
            with redirect_stderr(stderr):
                exit_code = handle_evolution_decide(
                    task_id="TF-bad",
                    claim=None,
                    repo_root=self.repo_root,
                )

        self.assertEqual(exit_code, 1)
        self.assertIn("error: task is not an evolution follow-up task", stderr.getvalue())

    def test_sisyphus_package_reexports_library_api(self) -> None:
        self.assertIs(sisyphus.request_task, request_task)
        self.assertIs(sisyphus.queue_conversation, queue_conversation)

    def test_legacy_taskflow_package_is_no_longer_available(self) -> None:
        with self.assertRaises(ModuleNotFoundError):
            importlib.import_module("taskflow")

    def test_config_uses_sisyphus_name(self) -> None:
        self.assertIsInstance(self.config, SisyphusConfig)

    def test_internal_sisyphus_path_helper_preserves_legacy_behavior(self) -> None:
        self.assertTrue(_is_internal_sisyphus_path(".planning"))
        self.assertTrue(_is_internal_sisyphus_path(".planning/tasks/demo"))
        self.assertFalse(_is_internal_sisyphus_path("README.md"))

    def test_detect_repo_root_prefers_sisyphus_config_file(self) -> None:
        nested = self.repo_root / "nested" / "child"
        nested.mkdir(parents=True, exist_ok=True)
        (self.repo_root / ".sisyphus.toml").write_text('base_branch = "canonical"\n', encoding="utf-8")

        with mock.patch("sisyphus.discovery.subprocess.run", side_effect=subprocess.CalledProcessError(1, ["git"])):
            resolved = detect_repo_root(nested)

        self.assertEqual(resolved, self.repo_root.resolve())

    def test_detect_repo_root_falls_back_to_taskflow_config_file(self) -> None:
        nested = self.repo_root / "legacy" / "child"
        nested.mkdir(parents=True, exist_ok=True)
        (self.repo_root / ".sisyphus.toml").unlink(missing_ok=True)

        with mock.patch("sisyphus.discovery.subprocess.run", side_effect=subprocess.CalledProcessError(1, ["git"])):
            resolved = detect_repo_root(nested)

        self.assertEqual(resolved, self.repo_root.resolve())

    def test_render_feature_plan_uses_sisyphus_verify_in_verification_mapping(self) -> None:
        rendered = _render_feature_plan({}, "Add dashboard", "Add an agent dashboard")

        self.assertIn("## Design Evaluation", rendered)
        self.assertIn("`Requested conversation workflow succeeds` -> `sisyphus verify`", rendered)
        self.assertNotIn("`Requested conversation workflow succeeds` -> `taskflow verify`", rendered)

    def test_render_issue_fix_plan_uses_sisyphus_verify_in_verification_mapping(self) -> None:
        rendered = _render_issue_fix_plan({}, "Fix dashboard", "Fix the broken dashboard")

        self.assertIn("## Design Evaluation", rendered)
        self.assertIn("`Regression scenario now passes` -> `sisyphus verify`", rendered)
        self.assertNotIn("`Regression scenario now passes` -> `taskflow verify`", rendered)

    def test_template_resources_are_packaged_under_canonical_sisyphus_package(self) -> None:
        root = template_root()

        self.assertTrue(root.joinpath("feature", "BRIEF.md").is_file())
        self.assertTrue(root.joinpath("feature", "PLAN.md").is_file())
        self.assertTrue(root.joinpath("issue", "BRIEF.md").is_file())
        self.assertTrue(root.joinpath("issue", "REPRO.md").is_file())

    def _init_git_repo(self, repo_root: Path, initial_branch: str) -> None:
        self._run_git(repo_root, "init", "-b", initial_branch)
        self._run_git(repo_root, "config", "user.email", "test@example.com")
        self._run_git(repo_root, "config", "user.name", "Test User")
        self._run_git(repo_root, "add", ".")
        self._run_git(repo_root, "commit", "-m", "initial")

    def _init_bare_remote(self, repo_root: Path, *, remote_name: str) -> Path:
        remote_path = Path(self.tempdir.name) / f"{remote_name}.git"
        self._run_git(remote_path.parent, "init", "--bare", str(remote_path))
        self._run_git(repo_root, "remote", "add", remote_name, str(remote_path))
        return remote_path

    def _run_git(self, cwd: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["git", *args],
            cwd=cwd,
            check=check,
            capture_output=True,
            text=True,
        )


if __name__ == "__main__":
    unittest.main()
