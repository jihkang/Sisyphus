from __future__ import annotations

from pathlib import Path
import unittest

from sisyphus.application.artifact_resources import FeatureArtifactResourceService
from sisyphus.application.ports.artifact_queries import FeatureArtifactReadModel


class ArtifactQueryFake:
    def __init__(self, *, snapshot=None, persisted_obligations=None) -> None:
        self.snapshot = snapshot
        self.persisted_obligations = persisted_obligations
        self.calls: list[tuple[object, ...]] = []

    def read_snapshot(self, task, task_dir):
        self.calls.append(("snapshot", dict(task), task_dir))
        return self.snapshot

    def project_current(self, task, task_dir, *, include_compiled_obligations):
        self.calls.append(("project", dict(task), task_dir, include_compiled_obligations))
        return FeatureArtifactReadModel(
            task_id="TF-1",
            feature_id="feature-1",
            artifact_graph={"graph": "current"},
            slot_bindings={"spec": {"slot_name": "spec"}},
            verification_claims=({"claim_id": "claim-1"},),
            promotion={"decision": "promotable"},
            invalidation={"status": "fresh"},
            derived_state="promotable",
            compiled_obligations={"obligation_count": 3},
        )

    def read_compiled_obligations(self, task_dir):
        self.calls.append(("obligations", task_dir))
        return self.persisted_obligations


class FeatureArtifactResourceServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.task = {"id": "TF-1", "type": "feature"}
        self.task_dir = Path("/repo/.planning/tasks/TF-1")

    def test_persisted_snapshot_is_used_without_reprojection(self) -> None:
        snapshot = {
            "task_id": "TF-1",
            "feature_id": "feature-1",
            "snapshot_status": {"status": "current"},
            "slot_bindings": {"spec": {"slot_name": "spec"}},
            "verification_claims": [{"claim_id": "claim-1"}],
            "evaluation": {
                "promotion": {"decision": "promotable"},
                "invalidation": {"status": "fresh"},
                "derived_state": "promotable",
            },
        }
        queries = ArtifactQueryFake(snapshot=snapshot)
        service = FeatureArtifactResourceService(queries)

        self.assertEqual(service.read(self.task, self.task_dir, "artifact-graph"), snapshot)
        self.assertEqual(
            service.read(self.task, self.task_dir, "promotion-summary"),
            {
                "task_id": "TF-1",
                "feature_id": "feature-1",
                "snapshot_status": {"status": "current"},
                "promotion": {"decision": "promotable"},
                "derived_state": "promotable",
            },
        )
        self.assertEqual([call[0] for call in queries.calls], ["snapshot", "snapshot"])

    def test_current_projection_shapes_each_resource(self) -> None:
        expected = {
            "artifact-graph": {"graph": "current"},
            "slot-bindings": {
                "task_id": "TF-1",
                "feature_id": "feature-1",
                "slot_bindings": {"spec": {"slot_name": "spec"}},
            },
            "verification-claims": {
                "task_id": "TF-1",
                "feature_id": "feature-1",
                "claims": [{"claim_id": "claim-1"}],
            },
            "promotion-summary": {
                "task_id": "TF-1",
                "feature_id": "feature-1",
                "promotion": {"decision": "promotable"},
                "derived_state": "promotable",
            },
            "invalidation-summary": {
                "task_id": "TF-1",
                "feature_id": "feature-1",
                "invalidation": {"status": "fresh"},
                "derived_state": "promotable",
            },
        }

        for resource_name, payload in expected.items():
            with self.subTest(resource_name=resource_name):
                queries = ArtifactQueryFake()
                service = FeatureArtifactResourceService(queries)
                self.assertEqual(service.read(self.task, self.task_dir, resource_name), payload)
                self.assertEqual(queries.calls[-1][-1], False)

    def test_compiled_obligations_preserve_projection_before_persisted_read(self) -> None:
        queries = ArtifactQueryFake(persisted_obligations={"obligation_count": 1})
        service = FeatureArtifactResourceService(queries)

        self.assertEqual(
            service.read(self.task, self.task_dir, "compiled-obligations"),
            {"obligation_count": 1},
        )
        self.assertEqual([call[0] for call in queries.calls], ["snapshot", "project", "obligations"])
        self.assertEqual(queries.calls[1][-1], True)

    def test_unsupported_resource_fails_before_query_effects(self) -> None:
        queries = ArtifactQueryFake()
        service = FeatureArtifactResourceService(queries)

        with self.assertRaisesRegex(ValueError, "unsupported feature task artifact resource"):
            service.read(self.task, self.task_dir, "unknown")

        self.assertEqual(queries.calls, [])


if __name__ == "__main__":
    unittest.main()
