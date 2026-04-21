from __future__ import annotations

import json
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
        tool_names = {tool["name"] for tool in self.core.list_tools()}
        resource_uris = {resource["uri"] for resource in self.core.list_resources()}

        self.assertIn("sisyphus.request_task", tool_names)
        self.assertIn("sisyphus.record_merged_pr", tool_names)
        self.assertIn("sisyphus.evolution_execute", tool_names)
        self.assertIn("sisyphus.evolution_followup_request", tool_names)
        self.assertIn("sisyphus.evolution_decide", tool_names)
        self.assertIn("sisyphus.evolution_run", tool_names)
        self.assertIn("sisyphus.evolution_status", tool_names)
        self.assertIn("sisyphus.evolution_report", tool_names)
        self.assertIn("sisyphus.evolution_compare", tool_names)
        self.assertIn("evolution://<run-id>/run", resource_uris)
        self.assertIn("evolution://<run-id>/status", resource_uris)
        self.assertIn("evolution://<run-id>/report", resource_uris)
        self.assertIn("evolution://compare/<left-run-id>/<right-run-id>", resource_uris)
        self.assertIn("task://<task-id>/conformance", resource_uris)
        self.assertIn("task://<task-id>/repro", resource_uris)
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
        self.assertEqual(record_payload["task"]["promotion"]["status"], "not_required")
        self.assertIn("# Brief", brief_payload)

    def test_task_record_resource_returns_doc_synced_projection_state(self) -> None:
        task = self._new_task("record-projection")
        task_dir = self.repo_root / task["task_dir"]
        (task_dir / "PLAN.md").write_text(
            "\n".join(
                [
                    "# Plan",
                    "",
                    "## Implementation Plan",
                    "",
                    "1. Normalize MCP task record projection.",
                    "",
                    "## Risks",
                    "",
                    "- Record resource could drift from PLAN.md.",
                    "",
                    "## Design Evaluation",
                    "",
                    "- Design Mode: `light`",
                    "- Decision Reason: `record resource should expose the normalized task state`",
                    "- Confidence: `high`",
                    "- Layer Impact: `layer-touching`",
                    "- Layer Decision Reason: `load_task_record backs the MCP resource surface`",
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
                    "- [x] Record resource exposes doc-synced strategy",
                    "",
                    "### Edge Cases",
                    "",
                    "- [x] Placeholder docs remain safe",
                    "",
                    "### Exception Cases",
                    "",
                    "- [x] Missing sections still load",
                    "",
                    "## Verification Mapping",
                    "",
                    "- `Record resource exposes doc-synced strategy` -> `unit_test`",
                    "- `Placeholder docs remain safe` -> `unit_test`",
                    "- `Missing sections still load` -> `unit_test`",
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

        record_payload = self.core.read_resource(f"task://{task['id']}/record")

        self.assertEqual(
            record_payload["task"]["test_strategy"]["normal_cases"][0]["name"],
            "Record resource exposes doc-synced strategy",
        )
        self.assertEqual(record_payload["task"]["design"]["mode"], "light")
        self.assertEqual(record_payload["task"]["design"]["required_artifacts"], ["boundary_note"])
        self.assertEqual(
            record_payload["task"]["design"]["artifacts"]["boundary_note"],
            "docs/adaptive-planning-protocol.md",
        )

    def test_list_tasks_projection_includes_promotion_summary(self) -> None:
        task = self._new_task("list-promotion")
        task_dir = self.repo_root / task["task_dir"]
        task_file = task_dir / "task.json"
        persisted = json.loads(task_file.read_text(encoding="utf-8"))
        persisted["promotion"] = {
            "required": True,
            "status": "pr_open",
            "strategy": "direct",
            "base_branch": "main",
            "head_branch": task["branch"],
            "pr_number": 41,
            "pr_url": "https://github.com/jihkang/Sisyphus/pull/41",
            "receipt_path": task["docs"]["promotion"],
        }
        task_file.write_text(json.dumps(persisted, indent=2) + "\n", encoding="utf-8")

        payload = self.core.read_resource("repo://status/tasks")
        task_payload = next(
            item for item in payload["tasks"] if (item.get("task_id") or item.get("id")) == task["id"]
        )

        self.assertEqual(task_payload["promotion"]["status"], "pr_open")
        self.assertEqual(task_payload["promotion"]["pr_number"], 41)
        self.assertEqual(task_payload["promotion"]["base_branch"], "main")

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

    def test_reads_placeholder_promotion_and_changeset_resources_before_merge(self) -> None:
        task = self._new_task("promotion-pending")

        promotion_payload = self.core.read_resource(f"task://{task['id']}/promotion")
        changeset_payload = self.core.read_resource(f"task://{task['id']}/changeset")

        self.assertEqual(promotion_payload["task_id"], task["id"])
        self.assertEqual(promotion_payload["status"], "not_recorded")
        self.assertEqual(promotion_payload["promotion"]["status"], "not_required")
        self.assertEqual(promotion_payload["promotion"]["receipt_path"], task["docs"]["promotion"])
        self.assertIn("# Changeset", changeset_payload)
        self.assertIn("`not_recorded`", changeset_payload)

    def test_reads_issue_repro_resource(self) -> None:
        task = create_task_record(
            repo_root=self.repo_root,
            config=self.config,
            task_type="issue",
            slug="issue-repro",
        )
        materialize_task_templates(task)

        repro_payload = self.core.read_resource(f"task://{task['id']}/repro")

        self.assertIn("# Repro", repro_payload)

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

    def test_task_record_resource_normalizes_closed_workflow_phase(self) -> None:
        task = self._new_task("closed-record-normalization")
        task_file = self.repo_root / task["task_dir"] / "task.json"
        persisted = json.loads(task_file.read_text(encoding="utf-8"))
        persisted["status"] = "closed"
        persisted["stage"] = "done"
        persisted["workflow_phase"] = "verified"
        persisted["verify_status"] = "passed"
        persisted["closed_at"] = "2026-04-21T12:31:44Z"
        task_file.write_text(json.dumps(persisted, indent=2) + "\n", encoding="utf-8")

        payload = self.core.read_resource(f"task://{task['id']}/record")

        self.assertEqual(payload["task"]["status"], "closed")
        self.assertEqual(payload["task"]["stage"], "done")
        self.assertEqual(payload["task"]["workflow_phase"], "closed")

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

    def test_reads_repo_metrics_resource(self) -> None:
        task = self._new_task("metrics")
        task_file = self.repo_root / task["task_dir"] / "task.json"
        persisted = json.loads(task_file.read_text(encoding="utf-8"))
        persisted["verify_status"] = "passed"
        persisted["last_verified_at"] = "2026-04-21T00:01:00Z"
        persisted["promotion"] = {
            "required": True,
            "status": "recorded",
            "strategy": "direct",
            "recorded_at": "2026-04-21T00:03:00Z",
            "receipt_path": persisted["docs"]["promotion"],
        }
        task_file.write_text(json.dumps(persisted, indent=2) + "\n", encoding="utf-8")

        event_path = self.repo_root / ".planning" / "events.jsonl"
        event_path.parent.mkdir(parents=True, exist_ok=True)
        event_path.write_text(
            "\n".join(
                [
                    json.dumps(
                        {
                            "event_id": "evt_resume",
                            "event_type": "conversation",
                            "status": "queued",
                            "timestamp": "2026-04-21T00:00:00Z",
                        }
                    ),
                    json.dumps(
                        {
                            "event_id": "evt_resume",
                            "event_type": "conversation",
                            "status": "processed",
                            "timestamp": "2026-04-21T00:00:05Z",
                        }
                    ),
                    new_event_envelope(
                        "verify.completed",
                        data={"task_id": task["id"], "status": "passed"},
                        timestamp="2026-04-21T00:01:00Z",
                    ).to_json(),
                    new_event_envelope(
                        "task.manual_intervention_required",
                        data={"task_id": task["id"], "reason": "promotion_required"},
                        timestamp="2026-04-21T00:01:30Z",
                    ).to_json(),
                ]
            )
            + "\n",
            encoding="utf-8",
        )

        metrics_payload = self.core.read_resource("repo://status/metrics")
        board_payload = self.core.read_resource("repo://status/board")

        self.assertEqual(metrics_payload["metrics"]["session_resume_time"]["sample_count"], 1)
        self.assertEqual(metrics_payload["metrics"]["promotion_lead_time"]["sample_count"], 1)
        self.assertEqual(metrics_payload["metrics"]["manual_intervention_count"]["count"], 1)
        self.assertEqual(board_payload["metrics"]["metrics"]["session_resume_time"]["sample_count"], 1)

    def test_reads_feature_artifact_resource_on_issue_task_as_unavailable(self) -> None:
        task = create_task_record(
            repo_root=self.repo_root,
            config=self.config,
            task_type="issue",
            slug="issue-artifact-resource",
        )
        materialize_task_templates(task)

        payload = self.core.read_resource(f"task://{task['id']}/artifact-graph")

        self.assertEqual(payload["task_id"], task["id"])
        self.assertEqual(payload["status"], "unavailable")
        self.assertIn("feature tasks", payload["reason"])

    def test_calls_and_reads_evolution_surface(self) -> None:
        self._write_evolution_run("EVR-mcp-alpha", target_ids=("execution-contract-wording",))
        self._write_evolution_run(
            "EVR-mcp-beta",
            target_ids=("execution-contract-wording", "mcp-tool-descriptions"),
            task_count=4,
            event_count=7,
            score_delta=0.40,
        )

        run_payload = self.core.call_tool("sisyphus.evolution_run", {"run_id": "EVR-mcp-alpha"})
        status_payload = self.core.call_tool("sisyphus.evolution_status", {"run_id": "EVR-mcp-alpha"})
        report_payload = self.core.call_tool("sisyphus.evolution_report", {"run_id": "EVR-mcp-alpha"})
        compare_payload = self.core.call_tool(
            "sisyphus.evolution_compare",
            {"left_run_id": "EVR-mcp-alpha", "right_run_id": "EVR-mcp-beta"},
        )

        self.assertEqual(run_payload["resource_uri"], "evolution://EVR-mcp-alpha/run")
        self.assertIn("final_stage: report_built", run_payload["content"])
        self.assertIn("Run ID: EVR-mcp-alpha", status_payload["content"])
        self.assertIn("# Evolution Report", report_payload["content"])
        self.assertEqual(compare_payload["resource_uri"], "evolution://compare/EVR-mcp-alpha/EVR-mcp-beta")
        self.assertIn("Dataset Tasks: 2 -> 4", compare_payload["content"])

        run_resource = self.core.read_resource("evolution://EVR-mcp-alpha/run")
        status_resource = self.core.read_resource("evolution://EVR-mcp-alpha/status")
        report_resource = self.core.read_resource("evolution://EVR-mcp-alpha/report")
        compare_resource = self.core.read_resource("evolution://compare/EVR-mcp-alpha/EVR-mcp-beta")

        self.assertIn("evolution run EVR-mcp-alpha", run_resource)
        self.assertIn("Run ID: EVR-mcp-alpha", status_resource)
        self.assertIn("# Evolution Report", report_resource)
        self.assertIn("Dataset Tasks: 2 -> 4", compare_resource)

    def test_calls_evolution_execute_tool(self) -> None:
        with mock.patch(
            "sisyphus.mcp_core.execute_evolution_surface",
            return_value=mock.Mock(
                ok=True,
                run_id="EVR-mcp-execute",
                resource_uri="evolution://EVR-mcp-execute/run",
                artifact_dir=str(self.repo_root / ".planning" / "evolution" / "runs" / "EVR-mcp-execute"),
                final_stage="report_built",
                failure_stage=None,
                content="evolution run EVR-mcp-execute\n",
                error=None,
                error_type=None,
            ),
        ) as mocked_execute:
            payload = self.core.call_tool(
                "sisyphus.evolution_execute",
                {
                    "run_id": "EVR-mcp-execute",
                    "target_ids": ["execution-contract-wording"],
                    "task_ids": ["TF-1"],
                    "max_events": 7,
                },
            )

        mocked_execute.assert_called_once()
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["run_id"], "EVR-mcp-execute")
        self.assertEqual(payload["resource_uri"], "evolution://EVR-mcp-execute/run")
        self.assertEqual(payload["final_stage"], "report_built")
        self.assertIn("evolution run EVR-mcp-execute", payload["content"])

    def test_calls_evolution_followup_request_tool(self) -> None:
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
        ) as mocked_request:
            payload = self.core.call_tool(
                "sisyphus.evolution_followup_request",
                {
                    "run_id": "EVR-followup",
                    "candidate_id": "candidate-001",
                    "title": "Request follow-up",
                    "summary": "Create a review-gated task.",
                    "requested_task_type": "feature",
                    "target_ids": ["execution-contract-wording"],
                    "owned_paths": ["docs/architecture.md"],
                    "review_gates": ["plan_review"],
                    "verification_obligations": [
                        {
                            "claim": "preserves intent",
                            "method": "sisyphus verify",
                            "required": True,
                        }
                    ],
                    "evidence_summary": [
                        {
                            "kind": "report",
                            "summary": "from evolution report",
                            "locator": "report.md",
                        }
                    ],
                },
            )

        mocked_request.assert_called_once()
        self.assertEqual(payload["task_id"], "TF-followup")
        self.assertEqual(payload["task_uri"], "task://TF-followup/record")
        self.assertEqual(payload["requested_targets"], ["execution-contract-wording"])
        self.assertEqual(payload["required_review_gates"], ["plan_review", "verify"])

    def test_calls_evolution_decide_tool(self) -> None:
        with mock.patch(
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
            payload = self.core.call_tool(
                "sisyphus.evolution_decide",
                {
                    "task_id": "TF-followup",
                    "claim": "candidate remains eligible",
                },
            )

        mocked_decide.assert_called_once()
        self.assertEqual(payload["task_id"], "TF-followup")
        self.assertEqual(payload["gate_status"], "eligible_for_promotion")
        self.assertEqual(payload["envelope_status"], "promotion")

    def test_missing_evolution_run_raises_clear_error(self) -> None:
        with self.assertRaises(FileNotFoundError):
            self.core.call_tool("sisyphus.evolution_run", {"run_id": "EVR-missing"})

        with self.assertRaises(FileNotFoundError):
            self.core.read_resource("evolution://EVR-missing/status")

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
        self.assertFalse(payload["close_attempted"])
        self.assertFalse(payload["closed"])
        self.assertIsNone(payload["close_status"])
        self.assertEqual(payload["close_gate_codes"], [])
        self.assertEqual(payload["child_retargeted_task_ids"], [])
        self.assertIsNone(payload["error"])

    def test_execute_promotion_tool_returns_open_pr_projection(self) -> None:
        fake_result = mock.Mock(
            ok=True,
            task_id="TF-123",
            status="pr_open",
            branch="feat/demo",
            base_branch="main",
            head_branch="feat/demo",
            commit_sha="abc123",
            pr_number=17,
            pr_url="https://github.com/jihkang/Sisyphus/pull/17",
            receipt_path=Path("/tmp/open_pr_receipt.json"),
            error=None,
        )

        with mock.patch("sisyphus.mcp_core.execute_promotion", return_value=fake_result):
            payload = self.core.call_tool(
                "sisyphus.execute_promotion",
                {
                    "task_id": "TF-123",
                    "repo_full_name": "jihkang/Sisyphus",
                },
            )

        self.assertTrue(payload["ok"])
        self.assertEqual(payload["task_id"], "TF-123")
        self.assertEqual(payload["status"], "pr_open")
        self.assertEqual(payload["commit_sha"], "abc123")
        self.assertEqual(payload["pr_number"], 17)
        self.assertEqual(payload["pr_url"], "https://github.com/jihkang/Sisyphus/pull/17")
        self.assertEqual(payload["receipt_path"], "/tmp/open_pr_receipt.json")
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
