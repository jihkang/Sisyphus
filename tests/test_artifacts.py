from __future__ import annotations

from pathlib import Path
import sys
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from sisyphus.artifacts import (
    ARTIFACT_RECORD_KIND_ATOMIC,
    ARTIFACT_RECORD_KIND_COMPOSITE,
    ARTIFACT_STATE_CANDIDATE,
    ARTIFACT_STATE_DRAFT,
    CollectionSlotBinding,
    FeatureChangeSlotBindings,
    INVARIANT_STATUS_PASSED,
    ArtifactInvariantRecord,
    ArtifactLineage,
    ArtifactRecord,
    ArtifactRef,
    CompositeArtifactRecord,
    NamedSlotBinding,
    TaskRunRef,
    TaskSpecRef,
    VerificationClaimRecord,
    load_artifact_record,
)


class ArtifactRecordTests(unittest.TestCase):
    maxDiff = None

    def test_minimal_artifact_record_round_trips_with_lineage_and_evidence_refs(self) -> None:
        record = ArtifactRecord(
            artifact_id="artifact-spec-001",
            artifact_type="feature_spec",
            state=ARTIFACT_STATE_DRAFT,
            payload={"acceptance": ["normal", "edge"], "feature_id": "feature/mobile-automation"},
            summary="feature spec draft",
            lineage=ArtifactLineage(
                repo_id="jihokang/Sisyphus",
                base_ref="main@48d9ee4",
                parent_artifacts=(
                    ArtifactRef("artifact-parent-001", "feature_request", revision="rev-1"),
                ),
            ),
            evidence_refs=(
                ArtifactRef("artifact-evidence-001", "discussion"),
                ArtifactRef("artifact-evidence-002", "design_note", revision="r2"),
            ),
        )

        serialized = record.to_dict()
        restored = ArtifactRecord.from_dict(serialized)
        generic = load_artifact_record(serialized)

        self.assertEqual(serialized["record_kind"], ARTIFACT_RECORD_KIND_ATOMIC)
        self.assertEqual(serialized["evidence_refs"][0]["artifact_id"], "artifact-evidence-001")
        self.assertEqual(restored, record)
        self.assertEqual(generic, record)

    def test_composite_artifact_record_preserves_reconstructable_envelope(self) -> None:
        record = CompositeArtifactRecord(
            artifact_id="artifact-feature-change-001",
            artifact_type="feature_change",
            state=ARTIFACT_STATE_CANDIDATE,
            payload={"selected_candidate": "artifact-impl-202"},
            summary="candidate feature change envelope",
            composition_rule="feature_change/v1",
            child_artifacts=(
                ArtifactRef("artifact-spec-123", "feature_spec"),
                ArtifactRef("artifact-impl-202", "implementation_candidate", revision="rev-b"),
            ),
            task_specs=(
                TaskSpecRef("TF-701", revision="spec-r1", doc_path=".planning/tasks/TF-701/PLAN.md"),
            ),
            task_runs=(
                TaskRunRef("TF-701", "run-801", "succeeded", receipt_locator=".planning/tasks/TF-701/receipts/run-801.json"),
                TaskRunRef("TF-701", "run-802", "succeeded"),
            ),
            lineage=ArtifactLineage(
                repo_id="jihokang/Sisyphus",
                base_ref="main@48d9ee4",
                parent_artifacts=(
                    ArtifactRef("artifact-spec-123", "feature_spec"),
                    ArtifactRef("artifact-impl-202", "implementation_candidate"),
                ),
            ),
            evidence_refs=(
                ArtifactRef("artifact-verify-401", "verification"),
            ),
            invariants=(
                ArtifactInvariantRecord("same-feature-id", INVARIANT_STATUS_PASSED),
                ArtifactInvariantRecord(
                    "selected-is-candidate",
                    INVARIANT_STATUS_PASSED,
                    detail="selected implementation remains a bound candidate",
                ),
            ),
        )

        serialized = record.to_dict()
        restored = CompositeArtifactRecord.from_dict(serialized)
        generic = load_artifact_record(serialized)

        self.assertEqual(serialized["record_kind"], ARTIFACT_RECORD_KIND_COMPOSITE)
        self.assertEqual(serialized["composition_rule"], "feature_change/v1")
        self.assertEqual([item["artifact_id"] for item in serialized["child_artifacts"]], ["artifact-spec-123", "artifact-impl-202"])
        self.assertEqual([item["task_id"] for item in serialized["task_runs"]], ["TF-701", "TF-701"])
        self.assertEqual(restored, record)
        self.assertEqual(generic, record)

    def test_optional_fields_remain_empty_but_stable(self) -> None:
        record = ArtifactRecord(
            artifact_id="artifact-empty-001",
            artifact_type="evidence",
            state=ARTIFACT_STATE_DRAFT,
        )

        serialized = record.to_dict()
        restored = ArtifactRecord.from_dict(serialized)

        self.assertEqual(serialized["payload"], {})
        self.assertEqual(serialized["evidence_refs"], [])
        self.assertNotIn("summary", serialized)
        self.assertNotIn("lineage", serialized)
        self.assertEqual(restored, record)

    def test_record_ordering_remains_deterministic_after_serialization(self) -> None:
        record = CompositeArtifactRecord(
            artifact_id="artifact-ordering-001",
            artifact_type="feature_change",
            state=ARTIFACT_STATE_CANDIDATE,
            payload={"z_key": 1, "a_key": 2},
            composition_rule="feature_change/v1",
            child_artifacts=(
                ArtifactRef("artifact-child-b", "implementation_candidate"),
                ArtifactRef("artifact-child-a", "feature_spec"),
            ),
            task_specs=(
                TaskSpecRef("TF-B"),
                TaskSpecRef("TF-A"),
            ),
            task_runs=(
                TaskRunRef("TF-B", "run-2", "succeeded"),
                TaskRunRef("TF-A", "run-1", "succeeded"),
            ),
            invariants=(
                ArtifactInvariantRecord("b-second", INVARIANT_STATUS_PASSED),
                ArtifactInvariantRecord("a-first", INVARIANT_STATUS_PASSED),
            ),
        )

        serialized = record.to_dict()

        self.assertEqual(list(serialized["payload"].keys()), ["a_key", "z_key"])
        self.assertEqual([item["artifact_id"] for item in serialized["child_artifacts"]], ["artifact-child-b", "artifact-child-a"])
        self.assertEqual([item["task_id"] for item in serialized["task_specs"]], ["TF-B", "TF-A"])
        self.assertEqual([item["run_id"] for item in serialized["task_runs"]], ["run-2", "run-1"])

    def test_invalid_identity_and_malformed_reconstruction_data_raise_actionable_errors(self) -> None:
        with self.assertRaisesRegex(ValueError, "artifact_record.artifact_id is required"):
            ArtifactRecord.from_dict(
                {
                    "record_kind": ARTIFACT_RECORD_KIND_ATOMIC,
                    "artifact_type": "feature_spec",
                    "state": ARTIFACT_STATE_DRAFT,
                }
            )

    def test_feature_change_slot_bindings_round_trip_named_and_collection_slots(self) -> None:
        bindings = FeatureChangeSlotBindings(
            spec=NamedSlotBinding(
                slot_name="spec",
                artifact=ArtifactRef("artifact-spec-123", "feature_spec"),
            ),
            implementation_candidates=CollectionSlotBinding(
                slot_name="implementation_candidates",
                artifacts=(
                    ArtifactRef("artifact-impl-201", "implementation_candidate"),
                    ArtifactRef("artifact-impl-202", "implementation_candidate"),
                ),
            ),
            selected_implementation=NamedSlotBinding(
                slot_name="selected_implementation",
                artifact=ArtifactRef("artifact-impl-202", "implementation_candidate"),
            ),
            tests=CollectionSlotBinding(
                slot_name="tests",
                artifacts=(
                    ArtifactRef("artifact-test-310", "test"),
                    ArtifactRef("artifact-test-311", "test"),
                ),
            ),
            verification_claims=CollectionSlotBinding(
                slot_name="verification_claims",
                artifacts=(ArtifactRef("artifact-verify-401", "verification"),),
            ),
        )

        serialized = bindings.to_dict()
        restored = FeatureChangeSlotBindings.from_dict(serialized)

        self.assertEqual(serialized["spec"]["slot_name"], "spec")
        self.assertEqual(
            [item["artifact_id"] for item in serialized["implementation_candidates"]["artifacts"]],
            ["artifact-impl-201", "artifact-impl-202"],
        )
        self.assertEqual(restored, bindings)

    def test_verification_claim_round_trips_with_dependencies_and_evidence(self) -> None:
        claim = VerificationClaimRecord(
            claim_id="claim-cross-001",
            claim="selected implementation satisfies current spec",
            scope="cross",
            dependency_refs=(
                ArtifactRef("artifact-spec-123", "feature_spec"),
                ArtifactRef("artifact-impl-202", "implementation_candidate", revision="rev-b"),
            ),
            evidence_refs=(
                ArtifactRef("artifact-verify-401", "verification"),
                ArtifactRef("artifact-receipt-601", "execution_receipt"),
            ),
        )

        serialized = claim.to_dict()
        restored = VerificationClaimRecord.from_dict(serialized)

        self.assertEqual([item["artifact_id"] for item in serialized["dependency_refs"]], ["artifact-spec-123", "artifact-impl-202"])
        self.assertEqual([item["artifact_id"] for item in serialized["evidence_refs"]], ["artifact-verify-401", "artifact-receipt-601"])
        self.assertEqual(restored, claim)

    def test_empty_collection_slots_remain_stable_and_serializable(self) -> None:
        bindings = FeatureChangeSlotBindings(
            spec=NamedSlotBinding(
                slot_name="spec",
                artifact=ArtifactRef("artifact-spec-123", "feature_spec"),
            ),
            implementation_candidates=CollectionSlotBinding(slot_name="implementation_candidates"),
        )

        serialized = bindings.to_dict()
        restored = FeatureChangeSlotBindings.from_dict(serialized)

        self.assertEqual(serialized["implementation_candidates"]["artifacts"], [])
        self.assertEqual(serialized["tests"]["artifacts"], [])
        self.assertEqual(serialized["verification_claims"]["artifacts"], [])
        self.assertEqual(restored, bindings)

    def test_collection_and_dependency_ordering_remains_deterministic(self) -> None:
        bindings = FeatureChangeSlotBindings(
            spec=NamedSlotBinding(
                slot_name="spec",
                artifact=ArtifactRef("artifact-spec-123", "feature_spec"),
            ),
            implementation_candidates=CollectionSlotBinding(
                slot_name="implementation_candidates",
                artifacts=(
                    ArtifactRef("artifact-impl-b", "implementation_candidate"),
                    ArtifactRef("artifact-impl-a", "implementation_candidate"),
                ),
            ),
            verification_claims=CollectionSlotBinding(
                slot_name="verification_claims",
                artifacts=(
                    ArtifactRef("artifact-verify-b", "verification"),
                    ArtifactRef("artifact-verify-a", "verification"),
                ),
            ),
        )
        claim = VerificationClaimRecord(
            claim_id="claim-order-001",
            claim="ordering is preserved",
            scope="cross",
            dependency_refs=(
                ArtifactRef("artifact-spec-123", "feature_spec"),
                ArtifactRef("artifact-impl-b", "implementation_candidate"),
                ArtifactRef("artifact-impl-a", "implementation_candidate"),
            ),
        )

        serialized_bindings = bindings.to_dict()
        serialized_claim = claim.to_dict()

        self.assertEqual(
            [item["artifact_id"] for item in serialized_bindings["implementation_candidates"]["artifacts"]],
            ["artifact-impl-b", "artifact-impl-a"],
        )
        self.assertEqual(
            [item["artifact_id"] for item in serialized_claim["dependency_refs"]],
            ["artifact-spec-123", "artifact-impl-b", "artifact-impl-a"],
        )

    def test_invalid_slot_binding_and_verification_claim_payloads_raise_actionable_errors(self) -> None:
        with self.assertRaisesRegex(ValueError, "named_slot_binding.slot_name is required"):
            NamedSlotBinding.from_dict(
                {
                    "artifact": {"artifact_id": "artifact-spec-123", "artifact_type": "feature_spec"},
                }
            )

        with self.assertRaisesRegex(TypeError, "verification_claim.dependency_refs must be a list, got str"):
            VerificationClaimRecord.from_dict(
                {
                    "claim_id": "claim-bad-001",
                    "claim": "bad dependency payload",
                    "scope": "cross",
                    "dependency_refs": "not-a-list",
                }
            )

        with self.assertRaisesRegex(TypeError, "artifact_record.child_artifacts must be a list, got str"):
            CompositeArtifactRecord.from_dict(
                {
                    "record_kind": ARTIFACT_RECORD_KIND_COMPOSITE,
                    "artifact_id": "artifact-bad-001",
                    "artifact_type": "feature_change",
                    "state": ARTIFACT_STATE_CANDIDATE,
                    "composition_rule": "feature_change/v1",
                    "child_artifacts": "not-a-list",
                }
            )

        with self.assertRaisesRegex(ValueError, "artifact_record.record_kind must be one of: artifact, composite"):
            load_artifact_record(
                {
                    "record_kind": "unknown",
                    "artifact_id": "artifact-bad-002",
                    "artifact_type": "feature_spec",
                    "state": ARTIFACT_STATE_DRAFT,
                }
            )


if __name__ == "__main__":
    unittest.main()
