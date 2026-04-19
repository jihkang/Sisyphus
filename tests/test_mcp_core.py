from __future__ import annotations

import tempfile
import unittest
from unittest import mock
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from sisyphus.api import record_merged_pull_request
from sisyphus.audit import run_verify
from sisyphus.config import load_config
from sisyphus.conformance import append_conformance_log
from sisyphus.events import new_event_envelope
from sisyphus.mcp_core import SisyphusMcpCoreService
from sisyphus.planning import approve_task_plan, freeze_task_spec
from sisyphus.state import create_task_record, save_task_record
from sisyphus.templates import materialize_task_templates


class McpCoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.repo_root = Path(self.tempdir.name)
        (self.repo_root / ".taskflow.toml").write_text("", encoding="utf-8")
        self.config = load_config(self.repo_root)
        self.core = SisyphusMcpCoreService(self.repo_root)

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def _new_task(self, slug: str = "mcp-core") -> dict:
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

    def test_lists_tools_and_resources(self) -> None:
        tool_names = {tool["name"] for tool in self.core.list_tools()}
        resource_uris = {resource["uri"] for resource in self.core.list_resources()}

        self.assertIn("sisyphus.request_task", tool_names)
        self.assertIn("sisyphus.record_merged_pr", tool_names)
        self.assertIn("task://<task-id>/conformance", resource_uris)
        self.assertIn("task://<task-id>/promotion", resource_uris)
        self.assertIn("task://<task-id>/changeset", resource_uris)
        self.assertIn("task://<task-id>/artifact-graph", resource_uris)
        self.assertIn("task://<task-id>/promotion-summary", resource_uris)
        request_tool = next(tool for tool in self.core.list_tools() if tool["name"] == "sisyphus.request_task")
        self.assertEqual(request_tool["inputSchema"]["required"], ["message"])
        self.assertFalse(request_tool["inputSchema"]["additionalProperties"])
        self.assertEqual(request_tool["outputSchema"]["properties"]["orchestrated"]["type"], "integer")
        self.assertIn("task", next(tool for tool in self.core.list_tools() if tool["name"] == "sisyphus.get_task")["outputSchema"]["properties"])

    def test_reads_task_resources(self) -> None:
        task = self._new_task("record")

        record_payload = self.core.read_resource(f"task://{task['id']}/record")
        brief_payload = self.core.read_resource(f"task://{task['id']}/brief")

        self.assertEqual(record_payload["task"]["id"], task["id"])
        self.assertIn("# Brief", brief_payload)

    def test_reads_task_promotion_and_changeset_resources(self) -> None:
        task = self._new_task("promotion")
        record_merged_pull_request(
            repo_root=self.repo_root,
            config=self.config,
            task_id=task["id"],
            branch=task["branch"],
            repo_full_name="jihkang/Sisyphus",
            pr_number=11,
            title="Remove live taskflow compatibility layer",
            changed_files=[{"path": "src/sisyphus/cli.py", "status": "modified"}],
        )

        promotion_payload = self.core.read_resource(f"task://{task['id']}/promotion")
        changeset_payload = self.core.read_resource(f"task://{task['id']}/changeset")

        self.assertEqual(promotion_payload["pull_request"]["number"], 11)
        self.assertIn("# Changeset", changeset_payload)
        self.assertIn("`src/sisyphus/cli.py`", changeset_payload)

    def test_reads_task_timeline_resource(self) -> None:
        task = self._new_task("timeline")
        task.setdefault("subtasks", []).append({"id": "S1", "title": "Wire MCP board", "category": "implementation"})
        append_conformance_log(
            task,
            checkpoint_type="spec_anchor",
            status="green",
            summary="spec anchored",
            source="tests",
            subtask_id="S1",
            resolved=True,
            drift=0,
        )
        append_conformance_log(
            task,
            checkpoint_type="post_exec",
            status="yellow",
            summary="verification mapping missing",
            source="tests",
            subtask_id="S1",
            resolved=False,
            drift=0,
        )
        save_task_record(self.repo_root / task["task_dir"] / "task.json", task)

        timeline_payload = self.core.read_resource(f"task://{task['id']}/timeline")

        self.assertEqual(timeline_payload["task_id"], task["id"])
        self.assertEqual(len(timeline_payload["task_history"]), 2)
        self.assertEqual(timeline_payload["subtasks"][0]["subtask_id"], "S1")
        self.assertEqual(len(timeline_payload["subtasks"][0]["history"]), 2)

    def test_reads_feature_task_artifact_resources(self) -> None:
        task = self._new_task("artifact-graph")
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
        run_verify(self.repo_root, self.config, task["id"])

        graph_payload = self.core.read_resource(f"task://{task['id']}/artifact-graph")
        slot_payload = self.core.read_resource(f"task://{task['id']}/slot-bindings")
        claim_payload = self.core.read_resource(f"task://{task['id']}/verification-claims")
        promotion_payload = self.core.read_resource(f"task://{task['id']}/promotion-summary")
        invalidation_payload = self.core.read_resource(f"task://{task['id']}/invalidation-summary")

        self.assertEqual(graph_payload["task_id"], task["id"])
        self.assertEqual(graph_payload["composite"]["artifact_type"], "feature_change")
        self.assertEqual(slot_payload["slot_bindings"]["spec"]["slot_name"], "spec")
        self.assertTrue(claim_payload["claims"])
        self.assertEqual(promotion_payload["promotion"]["decision"], "promotable")
        self.assertEqual(invalidation_payload["invalidation"]["status"], "fresh")

    def test_reads_repo_status_and_schema_resources(self) -> None:
        task = self._new_task("board")

        conformance_payload = self.core.read_resource("repo://status/conformance")
        board_payload = self.core.read_resource("repo://status/board")
        schema_payload = self.core.read_resource("repo://schema/mcp")

        self.assertEqual(conformance_payload["tasks"][0]["task_id"], task["id"])
        self.assertEqual(board_payload["summary"]["task_count"], 1)
        self.assertIn("# Sisyphus MCP Schema", schema_payload)
        self.assertIn("required: message", schema_payload)
        self.assertIn("returns: ok, event_id, task_id, event_status, orchestrated, error", schema_payload)

    def test_reads_recent_event_resource(self) -> None:
        event_path = self.repo_root / ".planning" / "events.jsonl"
        event_path.parent.mkdir(parents=True, exist_ok=True)
        event_path.write_text(
            "\n".join(
                [
                    new_event_envelope("task.created", data={"task_id": "TF-1"}, event_id="evt_1").to_json(),
                    new_event_envelope("task.updated", data={"task_id": "TF-1"}, event_id="evt_2").to_json(),
                ]
            )
            + "\n",
            encoding="utf-8",
        )

        payload = self.core.read_resource("repo://status/events")

        self.assertEqual(payload["events"][0]["event_id"], "evt_1")
        self.assertEqual(payload["events"][1]["event_id"], "evt_2")

    def test_calls_tool_against_repo_state(self) -> None:
        task = self._new_task("generate")
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

        payload = self.core.call_tool("sisyphus.subtasks_generate", {"task_id": task["id"]})

        self.assertEqual(payload["task_id"], task["id"])
        self.assertTrue(payload["subtasks"])

    def test_request_task_tool_returns_integer_orchestrated_count(self) -> None:
        fake_result = mock.Mock(
            ok=True,
            event_id="evt-123",
            task_id="TF-123",
            event_status="processed",
            orchestrated=0,
            error=None,
        )

        with mock.patch("sisyphus.mcp_core.request_task", return_value=fake_result):
            payload = self.core.call_tool("sisyphus.request_task", {"message": "create a task"})

        self.assertTrue(payload["ok"])
        self.assertEqual(payload["event_id"], "evt-123")
        self.assertEqual(payload["task_id"], "TF-123")
        self.assertEqual(payload["event_status"], "processed")
        self.assertEqual(payload["orchestrated"], 0)
        self.assertIsInstance(payload["orchestrated"], int)
        self.assertIsNone(payload["error"])

    def test_record_merged_pr_tool_returns_receipt_projection(self) -> None:
        task = self._new_task("promotion-tool")

        payload = self.core.call_tool(
            "sisyphus.record_merged_pr",
            {
                "task_id": task["id"],
                "branch": task["branch"],
                "repo_full_name": "jihkang/Sisyphus",
                "pr_number": 11,
                "title": "Remove live taskflow compatibility layer",
                "changed_files": [{"path": "src/sisyphus/cli.py", "status": "modified"}],
            },
        )

        self.assertTrue(payload["ok"])
        self.assertEqual(payload["task_id"], task["id"])
        self.assertEqual(payload["pr_number"], 11)
        self.assertIsNotNone(payload["receipt_path"])
        self.assertIsNotNone(payload["changeset_path"])
        self.assertIsNone(payload["error"])

    def test_request_task_tool_rejects_non_list_owned_paths(self) -> None:
        with self.assertRaisesRegex(TypeError, "expected list value, got: str"):
            self.core.call_tool(
                "sisyphus.request_task",
                {
                    "message": "create a task",
                    "owned_paths": "src/sisyphus",
                },
            )
