from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from sisyphus.application.evidence_queries import (
    evidence_resource_payload,
    summarize_evidence_graph,
)
from sisyphus.composition.evidence import collect_evidence_close_gates


class EvidenceQueryApplicationTests(unittest.TestCase):
    def test_missing_and_invalid_graphs_have_explicit_status(self) -> None:
        task = {
            "id": "TF-1",
            "verify_status": "passed",
            "meta": {"evidence_graph_required": True},
        }

        missing = summarize_evidence_graph(task, None, path="artifacts/evidence/evidence-graph.json")
        invalid = summarize_evidence_graph(
            task,
            None,
            read_error="malformed JSON",
            path="artifacts/evidence/evidence-graph.json",
        )

        self.assertEqual(missing["status"], "missing")
        self.assertEqual(invalid["status"], "invalid")
        self.assertEqual(invalid["error"], "malformed JSON")

    def test_resource_projection_returns_existing_graph_without_shape_drift(self) -> None:
        graph = {
            "schema_version": "sisyphus.evidence_graph.v1",
            "task_id": "TF-1",
            "curated_evidence": [],
            "unsupported_claims": [],
            "blocking_gaps": [],
            "extension": {"preserved": True},
        }

        payload = evidence_resource_payload(
            {"id": "TF-1"},
            graph,
            path="artifacts/evidence/evidence-graph.json",
        )

        self.assertEqual(payload, graph)
        self.assertIsNot(payload, graph)

    def test_close_gate_query_does_not_read_irrelevant_malformed_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            task_dir = Path(directory)
            path = task_dir / "artifacts" / "evidence" / "evidence-graph.json"
            path.parent.mkdir(parents=True)
            path.write_text("{not-json}\n", encoding="utf-8")

            gates = collect_evidence_close_gates(
                {"id": "TF-1", "verify_status": "not_run", "meta": {}},
                task_dir,
            )

        self.assertEqual(gates, [])


if __name__ == "__main__":
    unittest.main()
