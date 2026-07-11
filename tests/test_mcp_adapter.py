from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
import sys
from unittest import mock


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from sisyphus.mcp_adapter import call_mcp_tool, list_mcp_resources, list_mcp_tools, read_mcp_resource
from sisyphus.audit import run_verify
from sisyphus.planning import approve_task_plan, freeze_task_spec
from sisyphus.state import create_task_record
from sisyphus.templates import materialize_task_templates
from sisyphus.config import load_config


class McpAdapterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.repo_root = Path(self.tempdir.name)
        (self.repo_root / ".taskflow.toml").write_text("", encoding="utf-8")
        self.config = load_config(self.repo_root)

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def _new_task(self, slug: str = "mcp-task") -> dict:
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

    def _write_evolution_run(
        self,
        run_id: str,
        *,
        target_ids: tuple[str, ...],
        task_count: int = 2,
        event_count: int = 3,
        score_delta: float = 0.25,
    ) -> Path:
        artifact_dir = self.repo_root / ".planning" / "evolution" / "runs" / run_id
        artifact_dir.mkdir(parents=True, exist_ok=True)
        (artifact_dir / "run.json").write_text(
            json.dumps(
                {
                    "run": {
                        "run_id": run_id,
                        "repo_root": str(self.repo_root),
                        "target_ids": list(target_ids),
                        "selection_mode": "explicit",
                        "status": "planned",
                        "stage": "planned",
                    },
                    "artifact_dir": str(artifact_dir),
                    "entrypoint": "execute_evolution_run",
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        (artifact_dir / "dataset.json").write_text(
            json.dumps(
                {
                    "repo_root": str(self.repo_root),
                    "generated_at": "2026-04-20T00:00:00Z",
                    "event_log_path": str(self.repo_root / ".planning" / "events.jsonl"),
                    "selected_task_ids": [f"{run_id}-task-1", f"{run_id}-task-2"],
                    "task_traces": [],
                    "event_traces": [],
                    "task_count": task_count,
                    "event_count": event_count,
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        (artifact_dir / "harness_plan.json").write_text(
            json.dumps(
                {
                    "run_id": run_id,
                    "repo_root": str(self.repo_root),
                    "created_at": "2026-04-20T00:00:00Z",
                    "dataset_task_ids": [f"{run_id}-task-1", f"{run_id}-task-2"],
                    "dataset_event_count": event_count,
                    "baseline": {"evaluation_id": f"{run_id}:baseline", "role": "baseline"},
                    "candidate": {"evaluation_id": f"{run_id}:candidate", "role": "candidate"},
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        (artifact_dir / "constraints.json").write_text(
            json.dumps(
                {
                    "run_id": run_id,
                    "evaluated_at": "2026-04-20T00:00:00Z",
                    "status": "accepted",
                    "accepted": True,
                    "blocking_failure_count": 0,
                    "pending_guard_count": 0,
                    "checks": [],
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        (artifact_dir / "fitness.json").write_text(
            json.dumps(
                {
                    "run_id": run_id,
                    "evaluated_at": "2026-04-20T00:00:00Z",
                    "status": "scored",
                    "eligible_for_promotion": True,
                    "comparable_metric_count": 2,
                    "baseline_score": 0.62,
                    "candidate_score": 0.62 + score_delta,
                    "score_delta": score_delta,
                    "comparisons": [],
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        (artifact_dir / "report.md").write_text(
            "\n".join(
                [
                    "# Evolution Report",
                    "",
                    f"- Run ID: `{run_id}`",
                    "- Status: `ready_for_review`",
                    "- Recommendation: `review_candidate`",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        return artifact_dir

    def test_lists_tools_and_resources(self) -> None:
        tool_names = {tool["name"] for tool in list_mcp_tools()}
        resource_uris = {resource["uri"] for resource in list_mcp_resources()}

        self.assertIn("sisyphus.request_task", tool_names)
        self.assertIn("sisyphus.verify_task", tool_names)
        self.assertIn("sisyphus.evolution_execute", tool_names)
        self.assertIn("sisyphus.evolution_followup_request", tool_names)
        self.assertIn("sisyphus.evolution_decide", tool_names)
        self.assertIn("sisyphus.evolution_run", tool_names)
        self.assertIn("sisyphus.evolution_compare", tool_names)
        self.assertIn("repo://status/tasks", resource_uris)
        self.assertIn("evolution://<run-id>/run", resource_uris)
        self.assertIn("task://<task-id>/conformance", resource_uris)
        self.assertIn("task://<task-id>/repro", resource_uris)
        self.assertIn("task://<task-id>/artifact-graph", resource_uris)

    def test_read_task_record_and_conformance_resources(self) -> None:
        task = self._new_task("record")

        record_payload = read_mcp_resource(self.repo_root, f"task://{task['id']}/record")
        conformance_payload = read_mcp_resource(self.repo_root, f"task://{task['id']}/conformance")

        self.assertEqual(record_payload["task"]["id"], task["id"])
        self.assertEqual(conformance_payload["conformance"]["status"], "green")

    def test_read_task_markdown_resource(self) -> None:
        task = self._new_task("brief")

        brief = read_mcp_resource(self.repo_root, f"task://{task['id']}/brief")

        self.assertIn("# Brief", brief)

    def test_read_feature_task_artifact_graph_resource(self) -> None:
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

        payload = read_mcp_resource(self.repo_root, f"task://{task['id']}/artifact-graph")

        self.assertEqual(payload["task_id"], task["id"])
        self.assertEqual(payload["evaluation"]["derived_state"], "promotable")

    def test_call_get_task_and_list_tasks_tools(self) -> None:
        task = self._new_task("list")

        list_payload = call_mcp_tool(self.repo_root, "sisyphus.list_tasks")
        get_payload = call_mcp_tool(self.repo_root, "sisyphus.get_task", {"task_id": task["id"]})

        self.assertEqual(len(list_payload["tasks"]), 1)
        self.assertEqual(get_payload["task"]["id"], task["id"])

    def test_call_subtasks_generate_tool(self) -> None:
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

        payload = call_mcp_tool(self.repo_root, "sisyphus.subtasks_generate", {"task_id": task["id"]})

        self.assertEqual(payload["task_id"], task["id"])
        self.assertTrue(payload["subtasks"])

    def test_call_and_read_evolution_surface(self) -> None:
        self._write_evolution_run("EVR-adapter-left", target_ids=("execution-contract-wording",))
        self._write_evolution_run(
            "EVR-adapter-right",
            target_ids=("execution-contract-wording", "mcp-tool-descriptions"),
            task_count=4,
            event_count=6,
            score_delta=0.35,
        )

        run_payload = call_mcp_tool(self.repo_root, "sisyphus.evolution_run", {"run_id": "EVR-adapter-left"})
        compare_payload = call_mcp_tool(
            self.repo_root,
            "sisyphus.evolution_compare",
            {"left_run_id": "EVR-adapter-left", "right_run_id": "EVR-adapter-right"},
        )
        status_resource = read_mcp_resource(self.repo_root, "evolution://EVR-adapter-left/status")
        compare_resource = read_mcp_resource(self.repo_root, "evolution://compare/EVR-adapter-left/EVR-adapter-right")

        self.assertIn("final_stage: report_built", run_payload["content"])
        self.assertIn("Dataset Tasks: 2 -> 4", compare_payload["content"])
        self.assertIn("Run ID: EVR-adapter-left", status_resource)
        self.assertIn("Fitness Score Delta: +0.25 -> +0.35", compare_resource)

    def test_call_evolution_followup_and_decide_tools(self) -> None:
        with mock.patch(
            "sisyphus.mcp_core.request_evolution_followup",
            return_value=mock.Mock(
                task_id="TF-followup",
                task_uri="task://TF-followup/record",
                run_id="EVR-followup",
                candidate_id="candidate-001",
                requested_targets=("execution-contract-wording",),
                required_review_gates=("plan_review", "verify"),
                content="evolution followup request EVR-followup candidate-001\n",
            ),
        ) as mocked_request, mock.patch(
            "sisyphus.mcp_core.evaluate_evolution_followup_decision",
            return_value=mock.Mock(
                task_id="TF-followup",
                task_uri="task://TF-followup/record",
                run_id="EVR-followup",
                candidate_id="candidate-001",
                gate_status="eligible_for_promotion",
                envelope_status="promotion",
                content="evolution decision TF-followup\n",
            ),
        ) as mocked_decide:
            followup_payload = call_mcp_tool(
                self.repo_root,
                "sisyphus.evolution_followup_request",
                {
                    "run_id": "EVR-followup",
                    "candidate_id": "candidate-001",
                    "title": "Request follow-up",
                    "summary": "Create a review-gated task.",
                },
            )
            decision_payload = call_mcp_tool(
                self.repo_root,
                "sisyphus.evolution_decide",
                {"task_id": "TF-followup"},
            )

        mocked_request.assert_called_once()
        mocked_decide.assert_called_once()
        self.assertEqual(followup_payload["task_id"], "TF-followup")
        self.assertEqual(decision_payload["envelope_status"], "promotion")

    def test_missing_evolution_run_raises_not_found(self) -> None:
        with self.assertRaises(FileNotFoundError):
            call_mcp_tool(self.repo_root, "sisyphus.evolution_status", {"run_id": "EVR-missing"})

        with self.assertRaises(FileNotFoundError):
            read_mcp_resource(self.repo_root, "evolution://EVR-missing/report")


if __name__ == "__main__":
    unittest.main()
