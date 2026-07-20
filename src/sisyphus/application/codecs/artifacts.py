from __future__ import annotations

from collections.abc import Mapping

from ...domain.artifact.models import (
    ARTIFACT_RECORD_KIND_ATOMIC,
    ARTIFACT_RECORD_KIND_COMPOSITE,
    ARTIFACT_RECORD_SCHEMA_VERSION,
    VERIFICATION_CLAIM_STATUS_PASSED,
    ArtifactInvariantRecord,
    ArtifactLineage,
    ArtifactRecord,
    ArtifactRef,
    CollectionSlotBinding,
    CompositeArtifactRecord,
    FeatureChangeSlotBindings,
    NamedSlotBinding,
    TaskRunRef,
    TaskSpecRef,
    VerificationClaimRecord,
)
from .json_records import (
    decode_mapping_tuple,
    normalize_json_mapping,
    optional_string,
    reject_unknown_fields,
    require_mapping,
    require_string,
)


_ARTIFACT_REF_FIELDS = frozenset({"artifact_id", "artifact_type", "revision"})
_TASK_SPEC_REF_FIELDS = frozenset({"task_id", "revision", "doc_path"})
_TASK_RUN_REF_FIELDS = frozenset({"task_id", "run_id", "status", "receipt_locator"})
_LINEAGE_FIELDS = frozenset({"repo_id", "base_ref", "parent_artifacts"})
_INVARIANT_FIELDS = frozenset({"invariant_id", "status", "detail"})
_NAMED_SLOT_FIELDS = frozenset({"slot_name", "artifact"})
_COLLECTION_SLOT_FIELDS = frozenset({"slot_name", "artifacts"})
_FEATURE_SLOT_FIELDS = frozenset(
    {
        "spec",
        "implementation_candidates",
        "selected_implementation",
        "tests",
        "verification_claims",
        "approvals",
        "execution_receipts",
    }
)
_VERIFICATION_CLAIM_FIELDS = frozenset(
    {
        "claim_id",
        "claim",
        "scope",
        "status",
        "dependency_refs",
        "evidence_refs",
        "based_on_input_fingerprint",
    }
)
_COMMON_RECORD_FIELDS = frozenset(
    {
        "schema_version",
        "record_kind",
        "artifact_id",
        "artifact_type",
        "state",
        "payload",
        "summary",
        "lineage",
        "evidence_refs",
    }
)
_COMPOSITE_RECORD_FIELDS = _COMMON_RECORD_FIELDS | frozenset(
    {"composition_rule", "child_artifacts", "task_specs", "task_runs", "invariants"}
)


def encode_artifact_ref(value: ArtifactRef) -> dict[str, object]:
    data: dict[str, object] = {
        "artifact_id": value.artifact_id,
        "artifact_type": value.artifact_type,
    }
    if value.revision is not None:
        data["revision"] = value.revision
    return data


def decode_artifact_ref(raw: Mapping[str, object]) -> ArtifactRef:
    mapping = require_mapping(raw, "artifact_ref")
    reject_unknown_fields(mapping, _ARTIFACT_REF_FIELDS, "artifact_ref")
    return ArtifactRef(
        artifact_id=require_string(mapping.get("artifact_id"), "artifact_ref.artifact_id"),
        artifact_type=require_string(mapping.get("artifact_type"), "artifact_ref.artifact_type"),
        revision=optional_string(mapping.get("revision")),
    )


def encode_task_spec_ref(value: TaskSpecRef) -> dict[str, object]:
    data: dict[str, object] = {"task_id": value.task_id}
    if value.revision is not None:
        data["revision"] = value.revision
    if value.doc_path is not None:
        data["doc_path"] = value.doc_path
    return data


def decode_task_spec_ref(raw: Mapping[str, object]) -> TaskSpecRef:
    mapping = require_mapping(raw, "task_spec_ref")
    reject_unknown_fields(mapping, _TASK_SPEC_REF_FIELDS, "task_spec_ref")
    return TaskSpecRef(
        task_id=require_string(mapping.get("task_id"), "task_spec_ref.task_id"),
        revision=optional_string(mapping.get("revision")),
        doc_path=optional_string(mapping.get("doc_path")),
    )


def encode_task_run_ref(value: TaskRunRef) -> dict[str, object]:
    data: dict[str, object] = {
        "task_id": value.task_id,
        "run_id": value.run_id,
        "status": value.status,
    }
    if value.receipt_locator is not None:
        data["receipt_locator"] = value.receipt_locator
    return data


def decode_task_run_ref(raw: Mapping[str, object]) -> TaskRunRef:
    mapping = require_mapping(raw, "task_run_ref")
    reject_unknown_fields(mapping, _TASK_RUN_REF_FIELDS, "task_run_ref")
    return TaskRunRef(
        task_id=require_string(mapping.get("task_id"), "task_run_ref.task_id"),
        run_id=require_string(mapping.get("run_id"), "task_run_ref.run_id"),
        status=require_string(mapping.get("status"), "task_run_ref.status"),
        receipt_locator=optional_string(mapping.get("receipt_locator")),
    )


def encode_artifact_lineage(value: ArtifactLineage) -> dict[str, object]:
    data: dict[str, object] = {
        "parent_artifacts": [encode_artifact_ref(ref) for ref in value.parent_artifacts]
    }
    if value.repo_id is not None:
        data["repo_id"] = value.repo_id
    if value.base_ref is not None:
        data["base_ref"] = value.base_ref
    return data


def decode_artifact_lineage(raw: Mapping[str, object]) -> ArtifactLineage:
    mapping = require_mapping(raw, "lineage")
    reject_unknown_fields(mapping, _LINEAGE_FIELDS, "lineage")
    return ArtifactLineage(
        repo_id=optional_string(mapping.get("repo_id")),
        base_ref=optional_string(mapping.get("base_ref")),
        parent_artifacts=decode_mapping_tuple(
            mapping.get("parent_artifacts", []),
            decode_artifact_ref,
            "lineage.parent_artifacts",
        ),
    )


def encode_artifact_invariant(value: ArtifactInvariantRecord) -> dict[str, object]:
    data: dict[str, object] = {"invariant_id": value.invariant_id, "status": value.status}
    if value.detail is not None:
        data["detail"] = value.detail
    return data


def decode_artifact_invariant(raw: Mapping[str, object]) -> ArtifactInvariantRecord:
    mapping = require_mapping(raw, "invariant")
    reject_unknown_fields(mapping, _INVARIANT_FIELDS, "invariant")
    return ArtifactInvariantRecord(
        invariant_id=require_string(mapping.get("invariant_id"), "invariant.invariant_id"),
        status=require_string(mapping.get("status"), "invariant.status"),
        detail=optional_string(mapping.get("detail")),
    )


def encode_named_slot_binding(value: NamedSlotBinding) -> dict[str, object]:
    return {"slot_name": value.slot_name, "artifact": encode_artifact_ref(value.artifact)}


def decode_named_slot_binding(raw: Mapping[str, object]) -> NamedSlotBinding:
    mapping = require_mapping(raw, "named_slot_binding")
    reject_unknown_fields(mapping, _NAMED_SLOT_FIELDS, "named_slot_binding")
    return NamedSlotBinding(
        slot_name=require_string(mapping.get("slot_name"), "named_slot_binding.slot_name"),
        artifact=decode_artifact_ref(
            require_mapping(mapping.get("artifact"), "named_slot_binding.artifact")
        ),
    )


def encode_collection_slot_binding(value: CollectionSlotBinding) -> dict[str, object]:
    return {
        "slot_name": value.slot_name,
        "artifacts": [encode_artifact_ref(ref) for ref in value.artifacts],
    }


def decode_collection_slot_binding(raw: Mapping[str, object]) -> CollectionSlotBinding:
    mapping = require_mapping(raw, "collection_slot_binding")
    reject_unknown_fields(mapping, _COLLECTION_SLOT_FIELDS, "collection_slot_binding")
    return CollectionSlotBinding(
        slot_name=require_string(mapping.get("slot_name"), "collection_slot_binding.slot_name"),
        artifacts=decode_mapping_tuple(
            mapping.get("artifacts", []),
            decode_artifact_ref,
            "collection_slot_binding.artifacts",
        ),
    )


def encode_verification_claim(value: VerificationClaimRecord) -> dict[str, object]:
    data: dict[str, object] = {
        "claim_id": value.claim_id,
        "claim": value.claim,
        "scope": value.scope,
        "status": value.status,
        "dependency_refs": [encode_artifact_ref(ref) for ref in value.dependency_refs],
        "evidence_refs": [encode_artifact_ref(ref) for ref in value.evidence_refs],
    }
    if value.based_on_input_fingerprint is not None:
        data["based_on_input_fingerprint"] = value.based_on_input_fingerprint
    return data


def decode_verification_claim(raw: Mapping[str, object]) -> VerificationClaimRecord:
    mapping = require_mapping(raw, "verification_claim")
    reject_unknown_fields(mapping, _VERIFICATION_CLAIM_FIELDS, "verification_claim")
    return VerificationClaimRecord(
        claim_id=require_string(mapping.get("claim_id"), "verification_claim.claim_id"),
        claim=require_string(mapping.get("claim"), "verification_claim.claim"),
        scope=require_string(mapping.get("scope"), "verification_claim.scope"),
        status=optional_string(mapping.get("status")) or VERIFICATION_CLAIM_STATUS_PASSED,
        dependency_refs=decode_mapping_tuple(
            mapping.get("dependency_refs", []),
            decode_artifact_ref,
            "verification_claim.dependency_refs",
        ),
        evidence_refs=decode_mapping_tuple(
            mapping.get("evidence_refs", []),
            decode_artifact_ref,
            "verification_claim.evidence_refs",
        ),
        based_on_input_fingerprint=optional_string(mapping.get("based_on_input_fingerprint")),
    )


def encode_feature_change_slot_bindings(value: FeatureChangeSlotBindings) -> dict[str, object]:
    data: dict[str, object] = {
        "spec": encode_named_slot_binding(value.spec),
        "implementation_candidates": encode_collection_slot_binding(value.implementation_candidates),
        "tests": encode_collection_slot_binding(value.tests),
        "verification_claims": encode_collection_slot_binding(value.verification_claims),
        "approvals": encode_collection_slot_binding(value.approvals),
        "execution_receipts": encode_collection_slot_binding(value.execution_receipts),
    }
    if value.selected_implementation is not None:
        data["selected_implementation"] = encode_named_slot_binding(value.selected_implementation)
    return data


def decode_feature_change_slot_bindings(raw: Mapping[str, object]) -> FeatureChangeSlotBindings:
    mapping = require_mapping(raw, "feature_change_slot_bindings")
    reject_unknown_fields(mapping, _FEATURE_SLOT_FIELDS, "feature_change_slot_bindings")
    selected = mapping.get("selected_implementation")
    return FeatureChangeSlotBindings(
        spec=decode_named_slot_binding(
            require_mapping(mapping.get("spec"), "feature_change_slot_bindings.spec")
        ),
        implementation_candidates=decode_collection_slot_binding(
            require_mapping(
                mapping.get("implementation_candidates"),
                "feature_change_slot_bindings.implementation_candidates",
            )
        ),
        selected_implementation=(
            None
            if selected is None
            else decode_named_slot_binding(
                require_mapping(selected, "feature_change_slot_bindings.selected_implementation")
            )
        ),
        tests=_decode_default_collection(mapping, "tests"),
        verification_claims=_decode_default_collection(mapping, "verification_claims"),
        approvals=_decode_default_collection(mapping, "approvals"),
        execution_receipts=_decode_default_collection(mapping, "execution_receipts"),
    )


def encode_artifact_record(value: ArtifactRecord) -> dict[str, object]:
    data: dict[str, object] = {
        "schema_version": value.schema_version,
        "record_kind": value.record_kind,
        "artifact_id": value.artifact_id,
        "artifact_type": value.artifact_type,
        "state": value.state,
        "payload": normalize_json_mapping(value.payload, "payload"),
        "evidence_refs": [encode_artifact_ref(ref) for ref in value.evidence_refs],
    }
    if value.summary is not None:
        data["summary"] = value.summary
    if value.lineage is not None:
        data["lineage"] = encode_artifact_lineage(value.lineage)
    if isinstance(value, CompositeArtifactRecord):
        data.update(
            {
                "composition_rule": value.composition_rule,
                "child_artifacts": [encode_artifact_ref(ref) for ref in value.child_artifacts],
                "task_specs": [encode_task_spec_ref(ref) for ref in value.task_specs],
                "task_runs": [encode_task_run_ref(ref) for ref in value.task_runs],
                "invariants": [encode_artifact_invariant(item) for item in value.invariants],
            }
        )
    return data


def decode_artifact_record(raw: Mapping[str, object]) -> ArtifactRecord | CompositeArtifactRecord:
    mapping = require_mapping(raw, "artifact_record")
    record_kind = optional_string(mapping.get("record_kind"))
    if record_kind is None:
        record_kind = (
            ARTIFACT_RECORD_KIND_COMPOSITE
            if "composition_rule" in mapping or "child_artifacts" in mapping
            else ARTIFACT_RECORD_KIND_ATOMIC
        )
    if record_kind == ARTIFACT_RECORD_KIND_ATOMIC:
        return decode_atomic_artifact_record(mapping)
    if record_kind == ARTIFACT_RECORD_KIND_COMPOSITE:
        return decode_composite_artifact_record(mapping)
    raise ValueError(
        "artifact_record.record_kind must be one of: artifact, composite; "
        f"got {record_kind!r}"
    )


def decode_atomic_artifact_record(raw: Mapping[str, object]) -> ArtifactRecord:
    mapping = _validate_record(raw, _COMMON_RECORD_FIELDS, ARTIFACT_RECORD_KIND_ATOMIC)
    return ArtifactRecord(**_decode_common_record_fields(mapping))


def decode_composite_artifact_record(raw: Mapping[str, object]) -> CompositeArtifactRecord:
    mapping = _validate_record(raw, _COMPOSITE_RECORD_FIELDS, ARTIFACT_RECORD_KIND_COMPOSITE)
    return CompositeArtifactRecord(
        **_decode_common_record_fields(mapping),
        composition_rule=require_string(
            mapping.get("composition_rule"), "artifact_record.composition_rule"
        ),
        child_artifacts=decode_mapping_tuple(
            mapping.get("child_artifacts", []),
            decode_artifact_ref,
            "artifact_record.child_artifacts",
        ),
        task_specs=decode_mapping_tuple(
            mapping.get("task_specs", []), decode_task_spec_ref, "artifact_record.task_specs"
        ),
        task_runs=decode_mapping_tuple(
            mapping.get("task_runs", []), decode_task_run_ref, "artifact_record.task_runs"
        ),
        invariants=decode_mapping_tuple(
            mapping.get("invariants", []),
            decode_artifact_invariant,
            "artifact_record.invariants",
        ),
    )


def _decode_default_collection(
    mapping: Mapping[str, object], slot_name: str
) -> CollectionSlotBinding:
    return decode_collection_slot_binding(
        require_mapping(
            mapping.get(slot_name, {"slot_name": slot_name, "artifacts": []}),
            f"feature_change_slot_bindings.{slot_name}",
        )
    )


def _decode_common_record_fields(mapping: Mapping[str, object]) -> dict[str, object]:
    lineage_value = mapping.get("lineage")
    return {
        "artifact_id": require_string(mapping.get("artifact_id"), "artifact_record.artifact_id"),
        "artifact_type": require_string(mapping.get("artifact_type"), "artifact_record.artifact_type"),
        "state": require_string(mapping.get("state"), "artifact_record.state"),
        "payload": normalize_json_mapping(mapping.get("payload", {}), "artifact_record.payload"),
        "summary": optional_string(mapping.get("summary")),
        "lineage": (
            None
            if lineage_value is None
            else decode_artifact_lineage(
                require_mapping(lineage_value, "artifact_record.lineage")
            )
        ),
        "evidence_refs": decode_mapping_tuple(
            mapping.get("evidence_refs", []),
            decode_artifact_ref,
            "artifact_record.evidence_refs",
        ),
    }


def _validate_record(
    raw: Mapping[str, object],
    allowed_fields: frozenset[str],
    expected_kind: str,
) -> Mapping[str, object]:
    mapping = require_mapping(raw, "artifact_record")
    reject_unknown_fields(mapping, allowed_fields, "artifact_record")
    schema_version = optional_string(mapping.get("schema_version"))
    if schema_version not in (None, ARTIFACT_RECORD_SCHEMA_VERSION):
        raise ValueError(
            "artifact_record.schema_version must be "
            f"{ARTIFACT_RECORD_SCHEMA_VERSION!r}, got {schema_version!r}"
        )
    record_kind = optional_string(mapping.get("record_kind")) or expected_kind
    if record_kind != expected_kind:
        raise ValueError(
            f"artifact_record.record_kind must be {expected_kind!r}, got {record_kind!r}"
        )
    return mapping


__all__ = [
    "decode_artifact_invariant",
    "decode_artifact_lineage",
    "decode_artifact_record",
    "decode_artifact_ref",
    "decode_atomic_artifact_record",
    "decode_collection_slot_binding",
    "decode_composite_artifact_record",
    "decode_feature_change_slot_bindings",
    "decode_named_slot_binding",
    "decode_task_run_ref",
    "decode_task_spec_ref",
    "decode_verification_claim",
    "encode_artifact_invariant",
    "encode_artifact_lineage",
    "encode_artifact_record",
    "encode_artifact_ref",
    "encode_collection_slot_binding",
    "encode_feature_change_slot_bindings",
    "encode_named_slot_binding",
    "encode_task_run_ref",
    "encode_task_spec_ref",
    "encode_verification_claim",
]
