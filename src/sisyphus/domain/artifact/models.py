from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field


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

VERIFICATION_CLAIM_STATUS_PASSED = "passed"
VERIFICATION_CLAIM_STATUS_FAILED = "failed"
VERIFICATION_CLAIM_STATUS_PENDING = "pending"

@dataclass(frozen=True, slots=True)
class ArtifactRef:
    artifact_id: str
    artifact_type: str
    revision: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "artifact_id", _require_string(self.artifact_id, "artifact_id"))
        object.__setattr__(self, "artifact_type", _require_string(self.artifact_type, "artifact_type"))
        object.__setattr__(self, "revision", _optional_string(self.revision))

@dataclass(frozen=True, slots=True)
class TaskSpecRef:
    task_id: str
    revision: str | None = None
    doc_path: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "task_id", _require_string(self.task_id, "task_id"))
        object.__setattr__(self, "revision", _optional_string(self.revision))
        object.__setattr__(self, "doc_path", _optional_string(self.doc_path))

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

@dataclass(frozen=True, slots=True)
class ArtifactInvariantRecord:
    invariant_id: str
    status: str
    detail: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "invariant_id", _require_string(self.invariant_id, "invariant_id"))
        object.__setattr__(self, "status", _require_string(self.status, "status"))
        object.__setattr__(self, "detail", _optional_string(self.detail))

@dataclass(frozen=True, slots=True)
class NamedSlotBinding:
    slot_name: str
    artifact: ArtifactRef

    def __post_init__(self) -> None:
        object.__setattr__(self, "slot_name", _require_string(self.slot_name, "slot_name"))
        if not isinstance(self.artifact, ArtifactRef):
            raise TypeError(f"artifact must be ArtifactRef, got {type(self.artifact).__name__}")

@dataclass(frozen=True, slots=True)
class CollectionSlotBinding:
    slot_name: str
    artifacts: tuple[ArtifactRef, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "slot_name", _require_string(self.slot_name, "slot_name"))
        object.__setattr__(self, "artifacts", _coerce_tuple(self.artifacts, ArtifactRef, "artifacts"))

@dataclass(frozen=True, slots=True)
class VerificationClaimRecord:
    claim_id: str
    claim: str
    scope: str
    status: str = VERIFICATION_CLAIM_STATUS_PASSED
    dependency_refs: tuple[ArtifactRef, ...] = ()
    evidence_refs: tuple[ArtifactRef, ...] = ()
    based_on_input_fingerprint: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "claim_id", _require_string(self.claim_id, "claim_id"))
        object.__setattr__(self, "claim", _require_string(self.claim, "claim"))
        object.__setattr__(self, "scope", _require_string(self.scope, "scope"))
        object.__setattr__(self, "status", _require_string(self.status, "status"))
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
        object.__setattr__(self, "based_on_input_fingerprint", _optional_string(self.based_on_input_fingerprint))

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

@dataclass(frozen=True, slots=True)
class CompositeArtifactRecord(ArtifactRecord):
    composition_rule: str = ""
    child_artifacts: tuple[ArtifactRef, ...] = ()
    task_specs: tuple[TaskSpecRef, ...] = ()
    task_runs: tuple[TaskRunRef, ...] = ()
    invariants: tuple[ArtifactInvariantRecord, ...] = ()

    record_kind: str = field(init=False, default=ARTIFACT_RECORD_KIND_COMPOSITE)

    def __post_init__(self) -> None:
        # Zero-argument super() is unsafe for slotted dataclasses on Python 3.11-3.13.
        ArtifactRecord.__post_init__(self)
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
    "VERIFICATION_CLAIM_STATUS_FAILED",
    "VERIFICATION_CLAIM_STATUS_PASSED",
    "VERIFICATION_CLAIM_STATUS_PENDING",
]
