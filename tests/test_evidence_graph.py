from __future__ import annotations

import sys
from pathlib import Path
import tempfile
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from sisyphus.evidence_graph import (
    build_evidence_graph,
    collect_evidence_close_gates,
    read_evidence_graph,
    summarize_evidence_graph,
    write_evidence_graph,
)


class EvidenceGraphTests(unittest.TestCase):
    def test_build_write_read_and_summarize_supported_graph(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            task_dir = Path(tmp)
            (task_dir / "CHANGESET.md").write_text("# Changeset\n", encoding="utf-8")
            task = _verified_task()

            graph = build_evidence_graph(
                task,
                task_dir,
                [{"command": "python -m unittest", "status": "passed", "exit_code": 0, "output_excerpt": "OK"}],
                generated_at="2026-06-14T00:00:00Z",
            )
            path = write_evidence_graph(task_dir, graph)

            self.assertTrue(path.is_file())
            reloaded = read_evidence_graph(task_dir)
            assert reloaded is not None
            self.assertEqual(reloaded["schema_version"], "sisyphus.evidence_graph.v1")
            self.assertEqual(reloaded["task_id"], "TF-evidence")
            self.assertEqual(reloaded["blocking_gaps"], [])
            summary = summarize_evidence_graph(task, task_dir)
            self.assertEqual(summary["status"], "complete")
            self.assertGreaterEqual(summary["high_supported"], 1)
            self.assertEqual(collect_evidence_close_gates(task, task_dir), [])

    def test_partial_medium_evidence_does_not_block_close(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            task_dir = Path(tmp)
            task = _verified_task()
            task["conformance"] = {"status": "yellow", "unresolved_warning_count": 1, "history": []}

            graph = build_evidence_graph(
                task,
                task_dir,
                [{"command": "pytest", "status": "passed", "exit_code": 0}],
                generated_at="2026-06-14T00:00:00Z",
            )
            write_evidence_graph(task_dir, graph)

            summary = summarize_evidence_graph(task, task_dir)
            self.assertEqual(summary["status"], "complete")
            self.assertEqual(collect_evidence_close_gates(task, task_dir), [])

    def test_missing_evidence_only_blocks_new_verified_tasks(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            task_dir = Path(tmp)
            task = _verified_task()
            task["meta"] = {"evidence_graph_required": True}

            gates = collect_evidence_close_gates(task, task_dir)
            self.assertEqual({gate["code"] for gate in gates}, {"EVIDENCE_GRAPH_MISSING"})

            legacy_task = dict(task)
            legacy_task["meta"] = {}
            self.assertEqual(collect_evidence_close_gates(legacy_task, task_dir), [])

    def test_unsupported_high_importance_evidence_blocks_close(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            task_dir = Path(tmp)
            task = _verified_task()
            task["meta"] = {"evidence_graph_required": True}
            write_evidence_graph(
                task_dir,
                {
                    "schema_version": "sisyphus.evidence_graph.v1",
                    "task_id": task["id"],
                    "curated_evidence": [
                        {
                            "id": "ev-001",
                            "claim": "Unit tests pass.",
                            "verdict": "unsupported",
                            "importance": "high",
                            "blocking": True,
                        }
                    ],
                    "unsupported_claims": [],
                    "blocking_gaps": [],
                },
            )

            gates = collect_evidence_close_gates(task, task_dir)

            self.assertEqual({gate["code"] for gate in gates}, {"EVIDENCE_UNSUPPORTED_HIGH_IMPORTANCE"})


def _verified_task() -> dict[str, object]:
    return {
        "id": "TF-evidence",
        "type": "feature",
        "verify_status": "passed",
        "last_verified_at": "2026-06-14T00:00:00Z",
        "docs": {"changeset": "CHANGESET.md"},
        "conformance": {"status": "green", "history": []},
        "subtasks": [],
    }


if __name__ == "__main__":
    unittest.main()
