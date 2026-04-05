from __future__ import annotations

import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest import mock


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from taskflow.agents import AgentTrackingError, list_agents, register_agent, update_agent
from taskflow.api import queue_conversation, request_task
from taskflow.audit import run_verify
from taskflow.codex_prompt import build_codex_prompt
from taskflow.cli import (
    build_parser,
    handle_agent_run,
    handle_ingest_conversation,
    handle_request,
    handle_status,
    handle_subtasks_generate,
)
from taskflow.closeout import run_close
from taskflow.config import load_config
from taskflow.creation import TaskCreationError, create_task_workspace
from taskflow.daemon import process_inbox_event, queue_conversation_event, run_daemon
from taskflow.discord_bot import build_discord_source_context, queue_discord_conversation
from taskflow.paths import event_log_file, inbox_failed_dir, inbox_processed_dir
from taskflow.planning import approve_task_plan, freeze_task_spec, request_plan_changes, revise_task_plan
from taskflow.provider_wrapper import run_provider_wrapper
from taskflow.service import TaskNotificationTracker, build_task_update_summary, run_service_step
from taskflow.state import build_task_record, create_task_record, load_task_record
from taskflow.templates import materialize_task_templates
from taskflow.workflow import run_workflow_cycle
import sisyphus


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
        self.assertEqual(reloaded["gates"], [])
        self.assertEqual(reloaded["last_verify_results"][0]["status"], "passed")

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

        with mock.patch("taskflow.closeout.is_dirty_worktree", return_value=True):
            blocked = run_close(self.repo_root, self.config, task["id"], allow_dirty=False)
            closed = run_close(self.repo_root, self.config, task["id"], allow_dirty=True)

        self.assertFalse(blocked.closed)
        self.assertTrue(closed.closed)
        self.assertEqual(closed.gates, [])

        reloaded, _ = load_task_record(self.repo_root, self.config.task_dir, task["id"])
        self.assertEqual(reloaded["status"], "closed")
        self.assertEqual(reloaded["gates"], [])
        self.assertTrue(reloaded["meta"]["close_override_used"])

class TaskflowNewTests(unittest.TestCase):
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

    def test_create_task_rolls_back_on_template_failure(self) -> None:
        preview = build_task_record(self.repo_root, self.config, "feature", "rollback-check")

        with mock.patch("taskflow.creation.materialize_task_templates", side_effect=RuntimeError("boom")):
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


class TaskflowAgentTests(unittest.TestCase):
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
            owned_paths=["tests/test_taskflow.py"],
        )

        agents = list_agents(
            repo_root=self.repo_root,
            config=self.config,
            task_id=self.task["id"],
        )

        self.assertEqual(len(agents), 1)
        self.assertEqual(agents[0]["agent_id"], "worker-1")
        self.assertEqual(agents[0]["status"], "running")
        self.assertEqual(agents[0]["owned_paths"], ["tests/test_taskflow.py"])

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

        with mock.patch("taskflow.cli.Path.cwd", return_value=self.repo_root):
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
        with mock.patch("taskflow.cli.Path.cwd", return_value=self.repo_root):
            exit_code = handle_agent_run(
                task_id=self.task["id"],
                agent_id="worker-run-ok",
                role="worker",
                provider="codex",
                step="running codex wrapper",
                summary="spawned by wrapper",
                owned_paths=["src/taskflow/agents.py"],
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
        with mock.patch("taskflow.cli.Path.cwd", return_value=self.repo_root):
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

        with mock.patch("taskflow.cli.Path.cwd", return_value=self.repo_root):
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

        with mock.patch("taskflow.cli.Path.cwd", return_value=self.repo_root):
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

        self.assertEqual(prompt.task_id, self.task["id"])
        self.assertIn('"id":', prompt.prompt)
        self.assertIn('"test_strategy":', prompt.prompt)
        self.assertIn("Additional operator instruction: focus on the task docs", prompt.prompt)
        self.assertIn("## BRIEF (BRIEF.md)", prompt.prompt)

    def test_codex_wrapper_builds_default_codex_exec_command(self) -> None:
        with mock.patch("taskflow.provider_wrapper.Path.cwd", return_value=self.repo_root):
            with mock.patch("taskflow.provider_wrapper._resolve_codex_executable", return_value="codex.cmd"):
                with mock.patch("taskflow.cli.handle_agent_run", return_value=0) as mocked_run:
                    exit_code = run_provider_wrapper(
                        "codex",
                        [self.task["id"], "worker-codex"],
                    )

        self.assertEqual(exit_code, 0)
        kwargs = mocked_run.call_args.kwargs
        self.assertEqual(kwargs["provider"], "codex")
        self.assertEqual(kwargs["command"][:4], ["codex.cmd", "exec", "-C", str(self.repo_root)])
        self.assertEqual(kwargs["command"][-1], "-")
        self.assertIn("You are the local Codex worker for this task.", kwargs["stdin_text"])
        self.assertEqual(kwargs["env"]["GIT_CONFIG_KEY_0"], "safe.directory")
        self.assertEqual(kwargs["env"]["GIT_CONFIG_VALUE_0"], str(self.repo_root))

    def test_codex_wrapper_with_options_still_builds_default_launch(self) -> None:
        with mock.patch("taskflow.provider_wrapper.Path.cwd", return_value=self.repo_root):
            with mock.patch("taskflow.provider_wrapper._resolve_codex_executable", return_value="codex.cmd"):
                with mock.patch("taskflow.cli.handle_agent_run", return_value=0) as mocked_run:
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
        self.assertEqual(kwargs["role"], "worker")
        self.assertEqual(kwargs["command"][:4], ["codex.cmd", "exec", "-C", str(self.repo_root)])
        self.assertEqual(kwargs["command"][-1], "-")
        self.assertIn("Additional operator instruction: focus on the first subtask", kwargs["stdin_text"])
        self.assertEqual(kwargs["env"]["GIT_CONFIG_VALUE_0"], str(self.repo_root))

    def test_codex_wrapper_conversation_mode_creates_task_and_waits_for_plan_approval(self) -> None:
        subprocess.run(["git", "init", "-b", "main"], cwd=self.repo_root, check=True, capture_output=True, text=True)
        subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=self.repo_root, check=True, capture_output=True, text=True)
        subprocess.run(["git", "config", "user.name", "Test User"], cwd=self.repo_root, check=True, capture_output=True, text=True)
        subprocess.run(["git", "add", "."], cwd=self.repo_root, check=True, capture_output=True, text=True)
        subprocess.run(["git", "commit", "-m", "initial"], cwd=self.repo_root, check=True, capture_output=True, text=True)

        buffer = io.StringIO()
        with mock.patch("taskflow.provider_wrapper.Path.cwd", return_value=self.repo_root):
            with mock.patch("taskflow.daemon.run_provider_wrapper", return_value=0) as mocked_nested_run:
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
        with mock.patch("taskflow.cli.Path.cwd", return_value=self.repo_root):
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

        with mock.patch("taskflow.cli.detect_repo_root", return_value=self.repo_root):
            with mock.patch("taskflow.agent_runtime.subprocess.Popen", return_value=process) as mocked_popen:
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


class TaskflowDaemonTests(unittest.TestCase):
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
                        "- `Requested conversation workflow succeeds` -> `taskflow verify`",
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

        with mock.patch("taskflow.daemon.run_provider_wrapper", return_value=0) as mocked_wrapper:
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
        self.assertIn("Requested conversation workflow succeeds", (task_dir / "PLAN.md").read_text(encoding="utf-8"))
        self.assertEqual(task["meta"]["source_event_type"], "conversation")
        self.assertEqual(task["plan_status"], "pending_review")
        gate_codes = {gate["code"] for gate in task["gates"]}
        self.assertIn("PLAN_APPROVAL_REQUIRED", gate_codes)
        self.assertFalse(mocked_wrapper.called)
        self.assertFalse(persisted["result"]["auto_run"])
        self.assertEqual(persisted["result"]["agent_id"], None)

        log_lines = event_log_file(self.repo_root).read_text(encoding="utf-8").strip().splitlines()
        self.assertGreaterEqual(len(log_lines), 3)
        self.assertIn('"status": "processed"', log_lines[-1])

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
        with mock.patch("taskflow.cli.Path.cwd", return_value=self.repo_root):
            exit_code = handle_subtasks_generate(task["id"])

        self.assertEqual(freeze.spec_status, "frozen")
        self.assertEqual(exit_code, 0)
        persisted, _ = load_task_record(self.repo_root, self.config.task_dir, task["id"])
        self.assertEqual(persisted["workflow_phase"], "execution")
        self.assertEqual(len(persisted["subtasks"]), 3)
        self.assertEqual(persisted["subtasks"][0]["title"], "Happy path works")

    def test_run_daemon_once_respects_no_run_events(self) -> None:
        with mock.patch("taskflow.cli.Path.cwd", return_value=self.repo_root):
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
                no_run=True,
            )

        self.assertEqual(exit_code, 0)
        with mock.patch("taskflow.daemon.run_provider_wrapper", return_value=0) as mocked_wrapper:
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

    def test_run_daemon_once_orchestrates_task_until_closed(self) -> None:
        queue_conversation_event(
            self.repo_root,
            title="Add agent dashboard",
            message="show agent status in one place",
        )

        with mock.patch("taskflow.workflow.run_provider_wrapper", side_effect=self._fake_workflow_wrapper):
            stats = run_daemon(
                repo_root=self.repo_root,
                config=self.config,
                once=True,
                poll_interval_seconds=1,
            )

        self.assertGreaterEqual(stats.orchestrated, 1)
        processed_files = list(inbox_processed_dir(self.repo_root).glob("*.json"))
        self.assertEqual(len(processed_files), 1)
        persisted_event = json.loads(processed_files[0].read_text(encoding="utf-8"))
        task_id = persisted_event["result"]["task_id"]
        task, _ = load_task_record(self.repo_root, self.config.task_dir, task_id)
        self.assertEqual(task["status"], "closed")
        self.assertEqual(task["workflow_phase"], "closed")
        self.assertEqual(task["plan_status"], "approved")
        self.assertEqual(task["spec_status"], "frozen")
        self.assertTrue(all(subtask["status"] == "completed" for subtask in task["subtasks"]))

    def test_request_command_orchestrates_task_until_closed(self) -> None:
        buffer = io.StringIO()
        with mock.patch("taskflow.cli.Path.cwd", return_value=self.repo_root):
            with mock.patch("taskflow.workflow.run_provider_wrapper", side_effect=self._fake_workflow_wrapper):
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
                        no_run=False,
                    )

        self.assertEqual(exit_code, 0)
        rendered = buffer.getvalue()
        self.assertIn("request evt-", rendered)
        self.assertIn("status: closed", rendered)
        self.assertIn("spec_status: frozen", rendered)
        processed_files = list(inbox_processed_dir(self.repo_root).glob("*.json"))
        self.assertEqual(len(processed_files), 1)
        persisted_event = json.loads(processed_files[0].read_text(encoding="utf-8"))
        task_id = persisted_event["result"]["task_id"]
        task, _ = load_task_record(self.repo_root, self.config.task_dir, task_id)
        self.assertEqual(task["status"], "closed")
        self.assertEqual(task["workflow_phase"], "closed")

    def test_request_command_respects_no_run(self) -> None:
        buffer = io.StringIO()
        with mock.patch("taskflow.cli.Path.cwd", return_value=self.repo_root):
            with mock.patch("taskflow.workflow.run_provider_wrapper", side_effect=self._fake_workflow_wrapper) as mocked_wrapper:
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

    def test_workflow_cycle_stops_at_plan_review_limit(self) -> None:
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

        progressed_first = run_workflow_cycle(repo_root=self.repo_root, config=self.config)
        progressed_second = run_workflow_cycle(repo_root=self.repo_root, config=self.config)

        self.assertEqual(progressed_first, 1)
        self.assertEqual(progressed_second, 0)
        reloaded, _ = load_task_record(self.repo_root, self.config.task_dir, task["id"])
        self.assertEqual(reloaded["workflow_phase"], "needs_user_input")
        gate_codes = {gate["code"] for gate in reloaded["gates"]}
        self.assertIn("PLAN_REVIEW_LIMIT_REACHED", gate_codes)

    def test_process_inbox_event_moves_failure_to_failed_folder(self) -> None:
        _, event_path = queue_conversation_event(
            self.repo_root,
            title="Broken codex launch",
            message="로컬 codex 실행이 실패하는 경우도 남겨줘",
        )

        with mock.patch("taskflow.daemon.enforce_plan_approved", side_effect=lambda **kwargs: (True, load_task_record(self.repo_root, self.config.task_dir, kwargs["task_id"])[0])):
            with mock.patch("taskflow.daemon.enforce_spec_frozen", side_effect=lambda **kwargs: (True, load_task_record(self.repo_root, self.config.task_dir, kwargs["task_id"])[0])):
                with mock.patch("taskflow.daemon.run_provider_wrapper", return_value=7):
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
                "--no-run",
            ]
        )

        self.assertEqual(args.command, "request")
        self.assertEqual(args.message, "add agent dashboard")
        self.assertEqual(args.agent_id, "worker-1")
        self.assertTrue(args.no_run)

    def test_parser_accepts_serve_and_discord_bot_commands(self) -> None:
        parser = build_parser()

        serve_args = parser.parse_args(["serve", "--poll-interval-seconds", "7"])
        discord_args = parser.parse_args(
            ["discord-bot", "--token", "secret", "--channel-id", "12345", "--poll-interval-seconds", "9"]
        )

        self.assertEqual(serve_args.command, "serve")
        self.assertEqual(serve_args.poll_interval_seconds, 7)
        self.assertEqual(discord_args.command, "discord-bot")
        self.assertEqual(discord_args.token, "secret")
        self.assertEqual(discord_args.channel_ids, [12345])
        self.assertEqual(discord_args.poll_interval_seconds, 9)

    def test_sisyphus_package_reexports_library_api(self) -> None:
        self.assertIs(sisyphus.request_task, request_task)
        self.assertIs(sisyphus.queue_conversation, queue_conversation)

    def _init_git_repo(self, repo_root: Path, initial_branch: str) -> None:
        self._run_git(repo_root, "init", "-b", initial_branch)
        self._run_git(repo_root, "config", "user.email", "test@example.com")
        self._run_git(repo_root, "config", "user.name", "Test User")
        self._run_git(repo_root, "add", ".")
        self._run_git(repo_root, "commit", "-m", "initial")

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
