from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field

from .utils import find_unknown_fields

ARTIFACT_RECORD_SCHEMA_VERSION = "sisyphus.artifact_record.v1"
ARTIFACT_RECORD_KIND_ATOMIC = "artifact"
ARTIFACT_RECORD_KIND_COMPOSITE = "composite"

ARTIFACT_STATE_DRAFT = "draft"
ARTIFACT_STATE_CANDIDATE = "candidate"
ARTIFACT_STATE_VERIFIED = "verified"
ARTIFACT_STATE_PROMOTABLE = "promotable"
ARTIFACT_STATE_PROMOTED = "promoted"
ARTIFACT_STATE_INVALID = "invalid"
ARTIFACT_STATE_STALE = "stale"

INVARIANT_STATUS_PASSED = "passed"
INVARIANT_STATUS_FAILED = "failed"
INVARIANT_STATUS_PENDING = "pending"

_ARTIFACT_REF_FIELDS = frozenset({"artifact_id", "artifact_type", "revision"})
_TASK_SPEC_REF_FIELDS = frozenset({"task_id", "revision", "doc_path"})
_TASK_RUN_REF_FIELDS = frozenset({"task_id", "run_id", "status", "receipt_locator"})
_LINEAGE_FIELDS = frozenset({"repo_id", "base_ref", "parent_artifacts"})
_INVARIANT_FIELDS = frozenset({"invariant_id", "status", "detail"})
_NAMED_SLOT_BINDING_FIELDS = frozenset({"slot_name", "artifact"})
_COLLECTION_SLOT_BINDING_FIELDS = frozenset({"slot_name", "artifacts"})
_FEATURE_CHANGE_SLOT_BINDINGS_FIELDS = frozenset(
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
_VERIFICATION_CLAIM_FIELDS = frozenset({"claim_id", "claim", "scope", "dependency_refs", "evidence_refs"})
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
    {
        "composition_rule",
        "child_artifacts",
        "task_specs",
        "task_runs",
        "invariants",
    }
)


def load_artifact_record(raw: Mapping[str, object]) -> ArtifactRecord | CompositeArtifactRecord:
    mapping = _require_mapping(raw, "artifact_record")
    record_kind = _optional_string(mapping.get("record_kind"))
    if record_kind is None:
        if "composition_rule" in mapping or "child_artifacts" in mapping:
            record_kind = ARTIFACT_RECORD_KIND_COMPOSITE
        else:
            record_kind = ARTIFACT_RECORD_KIND_ATOMIC

    if record_kind == ARTIFACT_RECORD_KIND_ATOMIC:
        return ArtifactRecord.from_dict(mapping)
    if record_kind == ARTIFACT_RECORD_KIND_COMPOSITE:
        return CompositeArtifactRecord.from_dict(mapping)
    raise ValueError(f"artifact_record.record_kind must be one of: artifact, composite; got {record_kind!r}")


@dataclass(frozen=True, slots=True)
class ArtifactRef:
    artifact_id: str
    artifact_type: str
    revision: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "artifact_id", _require_string(self.artifact_id, "artifact_id"))
        object.__setattr__(self, "artifact_type", _require_string(self.artifact_type, "artifact_type"))
        object.__setattr__(self, "revision", _optional_string(self.revision))

    def to_dict(self) -> dict[str, object]:
        data: dict[str, object] = {
            "artifact_id": self.artifact_id,
            "artifact_type": self.artifact_type,
        }
        if self.revision is not None:
            data["revision"] = self.revision
        return data

    @classmethod
    def from_dict(cls, raw: Mapping[str, object]) -> ArtifactRef:
        mapping = _require_mapping(raw, "artifact_ref")
        _raise_unknown_fields(mapping, _ARTIFACT_REF_FIELDS, "artifact_ref")
        return cls(
            artifact_id=_require_string(mapping.get("artifact_id"), "artifact_ref.artifact_id"),
            artifact_type=_require_string(mapping.get("artifact_type"), "artifact_ref.artifact_type"),
            revision=_optional_string(mapping.get("revision")),
        )


@dataclass(frozen=True, slots=True)
class TaskSpecRef:
    task_id: str
    revision: str | None = None
    doc_path: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "task_id", _require_string(self.task_id, "task_id"))
        object.__setattr__(self, "revision", _optional_string(self.revision))
        object.__setattr__(self, "doc_path", _optional_string(self.doc_path))

    def to_dict(self) -> dict[str, object]:
        data: dict[str, object] = {
            "task_id": self.task_id,
        }
        if self.revision is not None:
            data["revision"] = self.revision
        if self.doc_path is not None:
            data["doc_path"] = self.doc_path
        return data

    @classmethod
    def from_dict(cls, raw: Mapping[str, object]) -> TaskSpecRef:
        mapping = _require_mapping(raw, "task_spec_ref")
        _raise_unknown_fields(mapping, _TASK_SPEC_REF_FIELDS, "task_spec_ref")
        return cls(
            task_id=_require_string(mapping.get("task_id"), "task_spec_ref.task_id"),
            revision=_optional_string(mapping.get("revision")),
            doc_path=_optional_string(mapping.get("doc_path")),
        )


@dataclass(frozen=True, slots=True)
class TaskRunRef:
    task_id: str
    run_id: str
    status: str
    receipt_locator: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "task_id", _require_string(self.task_id, "task_id"))
        object.__setattr__(self, "run_id", _require_string(self.run_id, "run_id"))
        object.__setattr__(self, "status", _require_string(self.status, "status"))
        object.__setattr__(self, "receipt_locator", _optional_string(self.receipt_locator))

    def to_dict(self) -> dict[str, object]:
        data: dict[str, object] = {
            "task_id": self.task_id,
            "run_id": self.run_id,
            "status": self.status,
        }
        if self.receipt_locator is not None:
            data["receipt_locator"] = self.receipt_locator
        return data

    @classmethod
    def from_dict(cls, raw: Mapping[str, object]) -> TaskRunRef:
        mapping = _require_mapping(raw, "task_run_ref")
        _raise_unknown_fields(mapping, _TASK_RUN_REF_FIELDS, "task_run_ref")
        return cls(
            task_id=_require_string(mapping.get("task_id"), "task_run_ref.task_id"),
            run_id=_require_string(mapping.get("run_id"), "task_run_ref.run_id"),
            status=_require_string(mapping.get("status"), "task_run_ref.status"),
            receipt_locator=_optional_string(mapping.get("receipt_locator")),
        )


@dataclass(frozen=True, slots=True)
class ArtifactLineage:
    repo_id: str | None = None
    base_ref: str | None = None
    parent_artifacts: tuple[ArtifactRef, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "repo_id", _optional_string(self.repo_id))
        object.__setattr__(self, "base_ref", _optional_string(self.base_ref))
        object.__setattr__(
            self,
            "parent_artifacts",
            _coerce_tuple(self.parent_artifacts, ArtifactRef, "parent_artifacts"),
        )

    def to_dict(self) -> dict[str, object]:
        data: dict[str, object] = {
            "parent_artifacts": [artifact.to_dict() for artifact in self.parent_artifacts],
        }
        if self.repo_id is not None:
            data["repo_id"] = self.repo_id
        if self.base_ref is not None:
            data["base_ref"] = self.base_ref
        return data

    @classmethod
    def from_dict(cls, raw: Mapping[str, object]) -> ArtifactLineage:
        mapping = _require_mapping(raw, "lineage")
        _raise_unknown_fields(mapping, _LINEAGE_FIELDS, "lineage")
        return cls(
            repo_id=_optional_string(mapping.get("repo_id")),
            base_ref=_optional_string(mapping.get("base_ref")),
            parent_artifacts=_load_tuple(
                mapping.get("parent_artifacts", []),
                ArtifactRef.from_dict,
                "lineage.parent_artifacts",
            ),
        )


@dataclass(frozen=True, slots=True)
class ArtifactInvariantRecord:
    invariant_id: str
    status: str
    detail: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "invariant_id", _require_string(self.invariant_id, "invariant_id"))
        object.__setattr__(self, "status", _require_string(self.status, "status"))
        object.__setattr__(self, "detail", _optional_string(self.detail))

    def to_dict(self) -> dict[str, object]:
        data: dict[str, object] = {
            "invariant_id": self.invariant_id,
            "status": self.status,
        }
        if self.detail is not None:
            data["detail"] = self.detail
        return data

    @classmethod
    def from_dict(cls, raw: Mapping[str, object]) -> ArtifactInvariantRecord:
        mapping = _require_mapping(raw, "invariant")
        _raise_unknown_fields(mapping, _INVARIANT_FIELDS, "invariant")
        return cls(
            invariant_id=_require_string(mapping.get("invariant_id"), "invariant.invariant_id"),
            status=_require_string(mapping.get("status"), "invariant.status"),
            detail=_optional_string(mapping.get("detail")),
        )


@dataclass(frozen=True, slots=True)
class NamedSlotBinding:
    slot_name: str
    artifact: ArtifactRef

    def __post_init__(self) -> None:
        object.__setattr__(self, "slot_name", _require_string(self.slot_name, "slot_name"))
        if not isinstance(self.artifact, ArtifactRef):
            raise TypeError(f"artifact must be ArtifactRef, got {type(self.artifact).__name__}")

    def to_dict(self) -> dict[str, object]:
        return {"slot_name": self.slot_name, "artifact": self.artifact.to_dict()}

    @classmethod
    def from_dict(cls, raw: Mapping[str, object]) -> NamedSlotBinding:
        mapping = _require_mapping(raw, "named_slot_binding")
        _raise_unknown_fields(mapping, _NAMED_SLOT_BINDING_FIELDS, "named_slot_binding")
        return cls(
            slot_name=_require_string(mapping.get("slot_name"), "named_slot_binding.slot_name"),
            artifact=ArtifactRef.from_dict(_require_mapping(mapping.get("artifact"), "named_slot_binding.artifact")),
        )


@dataclass(frozen=True, slots=True)
class CollectionSlotBinding:
    slot_name: str
    artifacts: tuple[ArtifactRef, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "slot_name", _require_string(self.slot_name, "slot_name"))
        object.__setattr__(self, "artifacts", _coerce_tuple(self.artifacts, ArtifactRef, "artifacts"))

    def to_dict(self) -> dict[str, object]:
        return {
            "slot_name": self.slot_name,
            "artifacts": [artifact.to_dict() for artifact in self.artifacts],
        }

    @classmethod
    def from_dict(cls, raw: Mapping[str, object]) -> CollectionSlotBinding:
        mapping = _require_mapping(raw, "collection_slot_binding")
        _raise_unknown_fields(mapping, _COLLECTION_SLOT_BINDING_FIELDS, "collection_slot_binding")
        return cls(
            slot_name=_require_string(mapping.get("slot_name"), "collection_slot_binding.slot_name"),
            artifacts=_load_tuple(
                mapping.get("artifacts", []),
                ArtifactRef.from_dict,
                "collection_slot_binding.artifacts",
            ),
        )


@dataclass(frozen=True, slots=True)
class VerificationClaimRecord:
    claim_id: str
    claim: str
    scope: str
    dependency_refs: tuple[ArtifactRef, ...] = ()
    evidence_refs: tuple[ArtifactRef, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "claim_id", _require_string(self.claim_id, "claim_id"))
        object.__setattr__(self, "claim", _require_string(self.claim, "claim"))
        object.__setattr__(self, "scope", _require_string(self.scope, "scope"))
        object.__setattr__(
            self,
            "dependency_refs",
            _coerce_tuple(self.dependency_refs, ArtifactRef, "dependency_refs"),
        )
        object.__setattr__(
            self,
            "evidence_refs",
            _coerce_tuple(self.evidence_refs, ArtifactRef, "evidence_refs"),
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "claim_id": self.claim_id,
            "claim": self.claim,
            "scope": self.scope,
            "dependency_refs": [artifact.to_dict() for artifact in self.dependency_refs],
            "evidence_refs": [artifact.to_dict() for artifact in self.evidence_refs],
        }

    @classmethod
    def from_dict(cls, raw: Mapping[str, object]) -> VerificationClaimRecord:
        mapping = _require_mapping(raw, "verification_claim")
        _raise_unknown_fields(mapping, _VERIFICATION_CLAIM_FIELDS, "verification_claim")
        return cls(
            claim_id=_require_string(mapping.get("claim_id"), "verification_claim.claim_id"),
            claim=_require_string(mapping.get("claim"), "verification_claim.claim"),
            scope=_require_string(mapping.get("scope"), "verification_claim.scope"),
            dependency_refs=_load_tuple(
                mapping.get("dependency_refs", []),
                ArtifactRef.from_dict,
                "verification_claim.dependency_refs",
            ),
            evidence_refs=_load_tuple(
                mapping.get("evidence_refs", []),
                ArtifactRef.from_dict,
                "verification_claim.evidence_refs",
            ),
        )


@dataclass(frozen=True, slots=True)
class FeatureChangeSlotBindings:
    spec: NamedSlotBinding
    implementation_candidates: CollectionSlotBinding
    selected_implementation: NamedSlotBinding | None = None
    tests: CollectionSlotBinding = field(default_factory=lambda: CollectionSlotBinding(slot_name="tests"))
    verification_claims: CollectionSlotBinding = field(
        default_factory=lambda: CollectionSlotBinding(slot_name="verification_claims")
    )
    approvals: CollectionSlotBinding = field(default_factory=lambda: CollectionSlotBinding(slot_name="approvals"))
    execution_receipts: CollectionSlotBinding = field(
        default_factory=lambda: CollectionSlotBinding(slot_name="execution_receipts")
    )

    def __post_init__(self) -> None:
        _require_named_slot(self.spec, "spec")
        _require_collection_slot(self.implementation_candidates, "implementation_candidates")
        if self.selected_implementation is not None:
            _require_named_slot(self.selected_implementation, "selected_implementation")
        _require_collection_slot(self.tests, "tests")
        _require_collection_slot(self.verification_claims, "verification_claims")
        _require_collection_slot(self.approvals, "approvals")
        _require_collection_slot(self.execution_receipts, "execution_receipts")

    def to_dict(self) -> dict[str, object]:
        data: dict[str, object] = {
            "spec": self.spec.to_dict(),
            "implementation_candidates": self.implementation_candidates.to_dict(),
            "tests": self.tests.to_dict(),
            "verification_claims": self.verification_claims.to_dict(),
            "approvals": self.approvals.to_dict(),
            "execution_receipts": self.execution_receipts.to_dict(),
        }
        if self.selected_implementation is not None:
            data["selected_implementation"] = self.selected_implementation.to_dict()
        return data

    @classmethod
    def from_dict(cls, raw: Mapping[str, object]) -> FeatureChangeSlotBindings:
        mapping = _require_mapping(raw, "feature_change_slot_bindings")
        _raise_unknown_fields(
            mapping,
            _FEATURE_CHANGE_SLOT_BINDINGS_FIELDS,
            "feature_change_slot_bindings",
        )
        selected_value = mapping.get("selected_implementation")
        return cls(
            spec=NamedSlotBinding.from_dict(_require_mapping(mapping.get("spec"), "feature_change_slot_bindings.spec")),
            implementation_candidates=CollectionSlotBinding.from_dict(
                _require_mapping(
                    mapping.get("implementation_candidates"),
                    "feature_change_slot_bindings.implementation_candidates",
                )
            ),
            selected_implementation=(
                None
                if selected_value is None
                else NamedSlotBinding.from_dict(
                    _require_mapping(selected_value, "feature_change_slot_bindings.selected_implementation")
                )
            ),
            tests=CollectionSlotBinding.from_dict(
                _require_mapping(mapping.get("tests", {"slot_name": "tests", "artifacts": []}), "feature_change_slot_bindings.tests")
            ),
            verification_claims=CollectionSlotBinding.from_dict(
                _require_mapping(
                    mapping.get(
                        "verification_claims",
                        {"slot_name": "verification_claims", "artifacts": []},
                    ),
                    "feature_change_slot_bindings.verification_claims",
                )
            ),
            approvals=CollectionSlotBinding.from_dict(
                _require_mapping(
                    mapping.get("approvals", {"slot_name": "approvals", "artifacts": []}),
                    "feature_change_slot_bindings.approvals",
                )
            ),
            execution_receipts=CollectionSlotBinding.from_dict(
                _require_mapping(
                    mapping.get(
                        "execution_receipts",
                        {"slot_name": "execution_receipts", "artifacts": []},
                    ),
                    "feature_change_slot_bindings.execution_receipts",
                )
            ),
        )


@dataclass(frozen=True, slots=True)
class ArtifactRecord:
    artifact_id: str
    artifact_type: str
    state: str
    payload: Mapping[str, object] = field(default_factory=dict)
    summary: str | None = None
    lineage: ArtifactLineage | None = None
    evidence_refs: tuple[ArtifactRef, ...] = ()

    record_kind: str = field(init=False, default=ARTIFACT_RECORD_KIND_ATOMIC)
    schema_version: str = field(init=False, default=ARTIFACT_RECORD_SCHEMA_VERSION)

    def __post_init__(self) -> None:
        object.__setattr__(self, "artifact_id", _require_string(self.artifact_id, "artifact_id"))
        object.__setattr__(self, "artifact_type", _require_string(self.artifact_type, "artifact_type"))
        object.__setattr__(self, "state", _require_string(self.state, "state"))
        object.__setattr__(self, "summary", _optional_string(self.summary))
        object.__setattr__(self, "payload", _normalize_payload(self.payload, "payload"))
        if self.lineage is not None and not isinstance(self.lineage, ArtifactLineage):
            raise TypeError(f"lineage must be an ArtifactLineage or None, got {type(self.lineage).__name__}")
        object.__setattr__(
            self,
            "evidence_refs",
            _coerce_tuple(self.evidence_refs, ArtifactRef, "evidence_refs"),
        )

    def to_dict(self) -> dict[str, object]:
        data: dict[str, object] = {
            "schema_version": self.schema_version,
            "record_kind": self.record_kind,
            "artifact_id": self.artifact_id,
            "artifact_type": self.artifact_type,
            "state": self.state,
            "payload": _normalize_payload(self.payload, "payload"),
            "evidence_refs": [artifact.to_dict() for artifact in self.evidence_refs],
        }
        if self.summary is not None:
            data["summary"] = self.summary
        if self.lineage is not None:
            data["lineage"] = self.lineage.to_dict()
        return data

    @classmethod
    def from_dict(cls, raw: Mapping[str, object]) -> ArtifactRecord:
        mapping = _validate_record_mapping(raw, _COMMON_RECORD_FIELDS, expected_kind=ARTIFACT_RECORD_KIND_ATOMIC)
        return cls(**_parse_common_record_fields(mapping))


@dataclass(frozen=True, slots=True)
class CompositeArtifactRecord(ArtifactRecord):
    composition_rule: str = ""
    child_artifacts: tuple[ArtifactRef, ...] = ()
    task_specs: tuple[TaskSpecRef, ...] = ()
    task_runs: tuple[TaskRunRef, ...] = ()
    invariants: tuple[ArtifactInvariantRecord, ...] = ()

    record_kind: str = field(init=False, default=ARTIFACT_RECORD_KIND_COMPOSITE)

    def __post_init__(self) -> None:
        super().__post_init__()
        object.__setattr__(self, "composition_rule", _require_string(self.composition_rule, "composition_rule"))
        object.__setattr__(
            self,
            "child_artifacts",
            _coerce_tuple(self.child_artifacts, ArtifactRef, "child_artifacts"),
        )
        object.__setattr__(
            self,
            "task_specs",
            _coerce_tuple(self.task_specs, TaskSpecRef, "task_specs"),
        )
        object.__setattr__(
            self,
            "task_runs",
            _coerce_tuple(self.task_runs, TaskRunRef, "task_runs"),
        )
        object.__setattr__(
            self,
            "invariants",
            _coerce_tuple(self.invariants, ArtifactInvariantRecord, "invariants"),
        )

    def to_dict(self) -> dict[str, object]:
        data = super().to_dict()
        data["composition_rule"] = self.composition_rule
        data["child_artifacts"] = [artifact.to_dict() for artifact in self.child_artifacts]
        data["task_specs"] = [task_spec.to_dict() for task_spec in self.task_specs]
        data["task_runs"] = [task_run.to_dict() for task_run in self.task_runs]
        data["invariants"] = [invariant.to_dict() for invariant in self.invariants]
        return data

    @classmethod
    def from_dict(cls, raw: Mapping[str, object]) -> CompositeArtifactRecord:
        mapping = _validate_record_mapping(raw, _COMPOSITE_RECORD_FIELDS, expected_kind=ARTIFACT_RECORD_KIND_COMPOSITE)
        common_fields = _parse_common_record_fields(mapping)
        return cls(
            **common_fields,
            composition_rule=_require_string(mapping.get("composition_rule"), "artifact_record.composition_rule"),
            child_artifacts=_load_tuple(
                mapping.get("child_artifacts", []),
                ArtifactRef.from_dict,
                "artifact_record.child_artifacts",
            ),
            task_specs=_load_tuple(
                mapping.get("task_specs", []),
                TaskSpecRef.from_dict,
                "artifact_record.task_specs",
            ),
            task_runs=_load_tuple(
                mapping.get("task_runs", []),
                TaskRunRef.from_dict,
                "artifact_record.task_runs",
            ),
            invariants=_load_tuple(
                mapping.get("invariants", []),
                ArtifactInvariantRecord.from_dict,
                "artifact_record.invariants",
            ),
        )


def _parse_common_record_fields(mapping: Mapping[str, object]) -> dict[str, object]:
    lineage_value = mapping.get("lineage")
    lineage = None if lineage_value is None else ArtifactLineage.from_dict(_require_mapping(lineage_value, "artifact_record.lineage"))
    return {
        "artifact_id": _require_string(mapping.get("artifact_id"), "artifact_record.artifact_id"),
        "artifact_type": _require_string(mapping.get("artifact_type"), "artifact_record.artifact_type"),
        "state": _require_string(mapping.get("state"), "artifact_record.state"),
        "payload": _normalize_payload(mapping.get("payload", {}), "artifact_record.payload"),
        "summary": _optional_string(mapping.get("summary")),
        "lineage": lineage,
        "evidence_refs": _load_tuple(
            mapping.get("evidence_refs", []),
            ArtifactRef.from_dict,
            "artifact_record.evidence_refs",
        ),
    }


def _require_named_slot(binding: NamedSlotBinding, expected_slot_name: str) -> None:
    if not isinstance(binding, NamedSlotBinding):
        raise TypeError(f"{expected_slot_name} must be NamedSlotBinding, got {type(binding).__name__}")
    if binding.slot_name != expected_slot_name:
        raise ValueError(f"{expected_slot_name} must use slot_name={expected_slot_name!r}, got {binding.slot_name!r}")


def _require_collection_slot(binding: CollectionSlotBinding, expected_slot_name: str) -> None:
    if not isinstance(binding, CollectionSlotBinding):
        raise TypeError(f"{expected_slot_name} must be CollectionSlotBinding, got {type(binding).__name__}")
    if binding.slot_name != expected_slot_name:
        raise ValueError(f"{expected_slot_name} must use slot_name={expected_slot_name!r}, got {binding.slot_name!r}")


def _validate_record_mapping(
    raw: Mapping[str, object],
    allowed_fields: frozenset[str],
    *,
    expected_kind: str,
) -> Mapping[str, object]:
    mapping = _require_mapping(raw, "artifact_record")
    _raise_unknown_fields(mapping, allowed_fields, "artifact_record")

    schema_version = _optional_string(mapping.get("schema_version"))
    if schema_version not in (None, ARTIFACT_RECORD_SCHEMA_VERSION):
        raise ValueError(
            "artifact_record.schema_version must be "
            f"{ARTIFACT_RECORD_SCHEMA_VERSION!r}, got {schema_version!r}"
        )

    record_kind = _optional_string(mapping.get("record_kind")) or expected_kind
    if record_kind != expected_kind:
        raise ValueError(
            f"artifact_record.record_kind must be {expected_kind!r}, got {record_kind!r}"
        )
    return mapping


def _raise_unknown_fields(
    mapping: Mapping[str, object],
    allowed_fields: frozenset[str],
    field_name: str,
) -> None:
    unknown = find_unknown_fields(mapping, allowed_fields)
    if unknown:
        joined = ", ".join(unknown)
        raise ValueError(f"{field_name} contains unknown fields: {joined}")


def _require_string(value: object, field_name: str) -> str:
    normalized = _optional_string(value)
    if normalized is None:
        raise ValueError(f"{field_name} is required")
    return normalized


def _optional_string(value: object) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip()
    return normalized or None


def _require_mapping(value: object, field_name: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise TypeError(f"{field_name} must be a mapping, got {type(value).__name__}")
    return value


def _require_list(value: object, field_name: str) -> list[object]:
    if not isinstance(value, list):
        raise TypeError(f"{field_name} must be a list, got {type(value).__name__}")
    return value


def _load_tuple(
    value: object,
    loader,
    field_name: str,
) -> tuple[object, ...]:
    items = _require_list(value, field_name)
    return tuple(loader(_require_mapping(item, f"{field_name}[{index}]")) for index, item in enumerate(items))


def _coerce_tuple(
    value: Sequence[object],
    expected_type: type,
    field_name: str,
) -> tuple[object, ...]:
    if isinstance(value, (str, bytes, bytearray)) or not isinstance(value, Sequence):
        raise TypeError(f"{field_name} must be a sequence of {expected_type.__name__}")
    normalized = []
    for index, item in enumerate(value):
        if not isinstance(item, expected_type):
            raise TypeError(
                f"{field_name}[{index}] must be {expected_type.__name__}, got {type(item).__name__}"
            )
        normalized.append(item)
    return tuple(normalized)


def _normalize_payload(value: object, field_name: str) -> dict[str, object]:
    mapping = _require_mapping(value, field_name)
    normalized: dict[str, object] = {}
    for key, item in sorted(mapping.items(), key=lambda pair: str(pair[0])):
        normalized[str(key)] = _normalize_json_value(item, f"{field_name}.{key}")
    return normalized


def _normalize_json_value(value: object, field_name: str) -> object:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Mapping):
        normalized: dict[str, object] = {}
        for key, item in sorted(value.items(), key=lambda pair: str(pair[0])):
            normalized[str(key)] = _normalize_json_value(item, f"{field_name}.{key}")
        return normalized
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [_normalize_json_value(item, f"{field_name}[{index}]") for index, item in enumerate(value)]
    raise TypeError(
        f"{field_name} must contain only JSON-serializable primitives, mappings, or lists; "
        f"got {type(value).__name__}"
    )


__all__ = [
    "ARTIFACT_RECORD_KIND_ATOMIC",
    "ARTIFACT_RECORD_KIND_COMPOSITE",
    "ARTIFACT_RECORD_SCHEMA_VERSION",
    "ARTIFACT_STATE_CANDIDATE",
    "ARTIFACT_STATE_DRAFT",
    "ARTIFACT_STATE_INVALID",
    "ARTIFACT_STATE_PROMOTABLE",
    "ARTIFACT_STATE_PROMOTED",
    "ARTIFACT_STATE_STALE",
    "ARTIFACT_STATE_VERIFIED",
    "INVARIANT_STATUS_FAILED",
    "INVARIANT_STATUS_PASSED",
    "INVARIANT_STATUS_PENDING",
    "CollectionSlotBinding",
    "ArtifactInvariantRecord",
    "ArtifactLineage",
    "ArtifactRecord",
    "ArtifactRef",
    "CompositeArtifactRecord",
    "FeatureChangeSlotBindings",
    "NamedSlotBinding",
    "TaskRunRef",
    "TaskSpecRef",
    "VerificationClaimRecord",
    "load_artifact_record",
]
