from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass

from .artifact_projection import FeatureTaskArtifactProjection
from .artifacts import (
    ARTIFACT_STATE_CANDIDATE,
    ARTIFACT_STATE_DRAFT,
    ARTIFACT_STATE_INVALID,
    ARTIFACT_STATE_PROMOTABLE,
    ARTIFACT_STATE_STALE,
    ARTIFACT_STATE_VERIFIED,
    INVARIANT_STATUS_FAILED,
    INVARIANT_STATUS_PENDING,
    ArtifactRecord,
    ArtifactRef,
    CompositeArtifactRecord,
    FeatureChangeSlotBindings,
    VerificationClaimRecord,
    VERIFICATION_CLAIM_STATUS_FAILED,
    VERIFICATION_CLAIM_STATUS_PASSED,
)

INVALIDATION_STATUS_FRESH = "fresh"
INVALIDATION_STATUS_STALE = "stale"
INVALIDATION_STATUS_INVALID = "invalid"

_DEFAULT_REQUIRED_TEST_CATEGORIES = ("normal", "edge", "exception")
_DEFAULT_REQUIRED_VERIFICATION_SCOPES = ("composite",)


@dataclass(frozen=True, slots=True)
class FeatureChangePolicy:
    required_test_categories: tuple[str, ...] = _DEFAULT_REQUIRED_TEST_CATEGORIES
    required_verification_scopes: tuple[str, ...] = _DEFAULT_REQUIRED_VERIFICATION_SCOPES
    require_approvals: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "required_test_categories",
            _normalize_string_tuple(self.required_test_categories, "required_test_categories"),
        )
        object.__setattr__(
            self,
            "required_verification_scopes",
            _normalize_string_tuple(self.required_verification_scopes, "required_verification_scopes"),
        )


@dataclass(frozen=True, slots=True)
class PromotionDecision:
    artifact_id: str
    decision: str
    missing_requirements: tuple[str, ...] = ()
    blocking_reasons: tuple[str, ...] = ()
    required_actions: tuple[str, ...] = ()
    evidence_refs: tuple[ArtifactRef, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "artifact_id", _require_string(self.artifact_id, "artifact_id"))
        object.__setattr__(self, "decision", _require_string(self.decision, "decision"))
        object.__setattr__(
            self,
            "missing_requirements",
            _normalize_string_tuple(self.missing_requirements, "missing_requirements"),
        )
        object.__setattr__(
            self,
            "blocking_reasons",
            _normalize_string_tuple(self.blocking_reasons, "blocking_reasons"),
        )
        object.__setattr__(
            self,
            "required_actions",
            _normalize_string_tuple(self.required_actions, "required_actions"),
        )
        object.__setattr__(
            self,
            "evidence_refs",
            _normalize_ref_tuple(self.evidence_refs, "evidence_refs"),
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "artifact_id": self.artifact_id,
            "decision": self.decision,
            "missing_requirements": list(self.missing_requirements),
            "blocking_reasons": list(self.blocking_reasons),
            "required_actions": list(self.required_actions),
            "evidence_refs": [ref.to_dict() for ref in self.evidence_refs],
        }


@dataclass(frozen=True, slots=True)
class InvalidationRecord:
    artifact_id: str
    status: str
    stale_inputs: tuple[ArtifactRef, ...] = ()
    invalid_inputs: tuple[ArtifactRef, ...] = ()
    reasons: tuple[str, ...] = ()
    required_actions: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "artifact_id", _require_string(self.artifact_id, "artifact_id"))
        object.__setattr__(self, "status", _require_string(self.status, "status"))
        object.__setattr__(
            self,
            "stale_inputs",
            _normalize_ref_tuple(self.stale_inputs, "stale_inputs"),
        )
        object.__setattr__(
            self,
            "invalid_inputs",
            _normalize_ref_tuple(self.invalid_inputs, "invalid_inputs"),
        )
        object.__setattr__(self, "reasons", _normalize_string_tuple(self.reasons, "reasons"))
        object.__setattr__(
            self,
            "required_actions",
            _normalize_string_tuple(self.required_actions, "required_actions"),
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "artifact_id": self.artifact_id,
            "status": self.status,
            "stale_inputs": [ref.to_dict() for ref in self.stale_inputs],
            "invalid_inputs": [ref.to_dict() for ref in self.invalid_inputs],
            "reasons": list(self.reasons),
            "required_actions": list(self.required_actions),
        }


@dataclass(frozen=True, slots=True)
class FeatureChangeEvaluation:
    artifact_id: str
    derived_state: str
    promotion: PromotionDecision
    invalidation: InvalidationRecord
    missing_requirements: tuple[str, ...] = ()
    failing_invariants: tuple[str, ...] = ()
    pending_invariants: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "artifact_id", _require_string(self.artifact_id, "artifact_id"))
        object.__setattr__(self, "derived_state", _require_string(self.derived_state, "derived_state"))
        object.__setattr__(
            self,
            "missing_requirements",
            _normalize_string_tuple(self.missing_requirements, "missing_requirements"),
        )
        object.__setattr__(
            self,
            "failing_invariants",
            _normalize_string_tuple(self.failing_invariants, "failing_invariants"),
        )
        object.__setattr__(
            self,
            "pending_invariants",
            _normalize_string_tuple(self.pending_invariants, "pending_invariants"),
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "artifact_id": self.artifact_id,
            "derived_state": self.derived_state,
            "missing_requirements": list(self.missing_requirements),
            "failing_invariants": list(self.failing_invariants),
            "pending_invariants": list(self.pending_invariants),
            "promotion": self.promotion.to_dict(),
            "invalidation": self.invalidation.to_dict(),
        }


def evaluate_feature_task_projection(
    projection: FeatureTaskArtifactProjection,
    *,
    policy: FeatureChangePolicy | None = None,
) -> FeatureChangeEvaluation:
    return evaluate_feature_change_artifact(
        projection.feature_change_artifact,
        slot_bindings=projection.slot_bindings,
        verification_claims=projection.verification_claims,
        artifacts=projection.atomic_artifacts(),
        policy=policy,
    )


def evaluate_feature_change_artifact(
    feature_change_artifact: CompositeArtifactRecord,
    *,
    slot_bindings: FeatureChangeSlotBindings | None = None,
    verification_claims: Sequence[VerificationClaimRecord] | None = None,
    artifacts: Sequence[ArtifactRecord] = (),
    policy: FeatureChangePolicy | None = None,
) -> FeatureChangeEvaluation:
    if feature_change_artifact.artifact_type != "feature_change":
        raise ValueError(
            "feature change evaluation requires artifact_type='feature_change', "
            f"got {feature_change_artifact.artifact_type!r}"
        )

    resolved_policy = policy or FeatureChangePolicy()
    resolved_bindings = slot_bindings or _slot_bindings_from_payload(feature_change_artifact)
    resolved_claims = tuple(verification_claims or _verification_claims_from_payload(feature_change_artifact))
    artifacts_by_id = {artifact.artifact_id: artifact for artifact in artifacts}

    missing_requirements: list[str] = []
    blocking_reasons: list[str] = []
    required_actions: list[str] = []
    failing_invariants: list[str] = []
    pending_invariants: list[str] = []

    candidate_ids = {ref.artifact_id for ref in resolved_bindings.implementation_candidates.artifacts}
    spec_ref = resolved_bindings.spec.artifact
    selected_ref = None if resolved_bindings.selected_implementation is None else resolved_bindings.selected_implementation.artifact
    test_refs = resolved_bindings.tests.artifacts
    approval_refs = resolved_bindings.approvals.artifacts

    if not candidate_ids:
        missing_requirements.append("implementation_candidates")
        required_actions.append("bind_implementation_candidates")

    if selected_ref is None:
        missing_requirements.append("selected_implementation")
        required_actions.append("select_implementation")
    elif selected_ref.artifact_id not in candidate_ids:
        blocking_reasons.append("selected_implementation_not_in_candidates")
        required_actions.append("reselect_implementation")

    required_test_categories = set(resolved_policy.required_test_categories)
    present_test_categories = _test_categories(test_refs, artifacts_by_id)
    for category in sorted(required_test_categories - present_test_categories):
        missing_requirements.append(f"test:{category}")
    if required_test_categories - present_test_categories:
        required_actions.append("bind_required_tests")

    passed_scopes: set[str] = set()
    for claim in resolved_claims:
        if claim.status == VERIFICATION_CLAIM_STATUS_FAILED:
            blocking_reasons.append(f"verification_claim_failed:{claim.claim_id}")
        elif claim.status == VERIFICATION_CLAIM_STATUS_PASSED:
            if not _claim_binds_current_inputs(
                claim,
                spec_ref=spec_ref,
                selected_ref=selected_ref,
                test_refs=test_refs,
            ):
                blocking_reasons.append(f"verification_claim_dependency_mismatch:{claim.claim_id}")
                required_actions.append("reverify_required_claims")
                continue
            passed_scopes.add(claim.scope)

    required_scopes = set(resolved_policy.required_verification_scopes)
    for scope in sorted(required_scopes - passed_scopes):
        missing_requirements.append(f"verification_scope:{scope}")
    if required_scopes - passed_scopes:
        required_actions.append("verify_required_claims")

    if resolved_policy.require_approvals and not approval_refs:
        missing_requirements.append("approvals")
        required_actions.append("collect_approvals")

    for invariant in feature_change_artifact.invariants:
        if invariant.status == INVARIANT_STATUS_FAILED:
            failing_invariants.append(invariant.invariant_id)
        elif invariant.status == INVARIANT_STATUS_PENDING:
            pending_invariants.append(invariant.invariant_id)
    if failing_invariants:
        blocking_reasons.extend(f"invariant_failed:{item}" for item in failing_invariants)
        required_actions.append("recompose_feature_change")

    stale_inputs: list[ArtifactRef] = []
    invalid_inputs: list[ArtifactRef] = []
    invalidation_reasons: list[str] = []
    for ref in _iter_referenced_artifacts(feature_change_artifact, resolved_bindings):
        artifact = artifacts_by_id.get(ref.artifact_id)
        if artifact is None:
            continue
        if artifact.state == ARTIFACT_STATE_INVALID:
            invalid_inputs.append(ref)
            invalidation_reasons.append(f"invalid_input:{ref.artifact_id}")
            continue
        if artifact.state == ARTIFACT_STATE_STALE:
            stale_inputs.append(ref)
            invalidation_reasons.append(f"stale_input:{ref.artifact_id}")
            continue
        if _lineage_mismatch(feature_change_artifact, artifact):
            stale_inputs.append(ref)
            invalidation_reasons.append(f"lineage_mismatch:{ref.artifact_id}")

    invalidation_reasons.extend(f"invariant_failed:{item}" for item in failing_invariants)
    invalidation_reasons.extend(blocking_reasons)

    if invalid_inputs:
        required_actions.append("replace_invalid_inputs")
    if stale_inputs:
        required_actions.append("reverify_stale_inputs")

    has_candidate_shape = bool(spec_ref.artifact_id) and bool(candidate_ids)
    verification_ready = (
        has_candidate_shape
        and selected_ref is not None
        and not any(item.startswith("verification_scope:") for item in missing_requirements)
        and not failing_invariants
        and not invalid_inputs
        and not blocking_reasons
    )
    promotable_ready = (
        verification_ready
        and not stale_inputs
        and not pending_invariants
        and not any(item.startswith("test:") for item in missing_requirements)
        and (not resolved_policy.require_approvals or bool(approval_refs))
    )

    if failing_invariants or invalid_inputs or blocking_reasons:
        derived_state = ARTIFACT_STATE_INVALID
    elif stale_inputs:
        derived_state = ARTIFACT_STATE_STALE
    elif not has_candidate_shape:
        derived_state = ARTIFACT_STATE_DRAFT
    elif promotable_ready:
        derived_state = ARTIFACT_STATE_PROMOTABLE
    elif verification_ready:
        derived_state = ARTIFACT_STATE_VERIFIED
    else:
        derived_state = ARTIFACT_STATE_CANDIDATE

    invalidation_status = INVALIDATION_STATUS_FRESH
    if invalid_inputs or failing_invariants or blocking_reasons:
        invalidation_status = INVALIDATION_STATUS_INVALID
    elif stale_inputs:
        invalidation_status = INVALIDATION_STATUS_STALE

    promotion = PromotionDecision(
        artifact_id=feature_change_artifact.artifact_id,
        decision=derived_state,
        missing_requirements=tuple(dict.fromkeys(missing_requirements)),
        blocking_reasons=tuple(dict.fromkeys(blocking_reasons)),
        required_actions=tuple(dict.fromkeys(required_actions)),
        evidence_refs=feature_change_artifact.evidence_refs,
    )
    invalidation = InvalidationRecord(
        artifact_id=feature_change_artifact.artifact_id,
        status=invalidation_status,
        stale_inputs=tuple(_unique_refs(stale_inputs)),
        invalid_inputs=tuple(_unique_refs(invalid_inputs)),
        reasons=tuple(dict.fromkeys(invalidation_reasons)),
        required_actions=tuple(dict.fromkeys(required_actions)),
    )
    return FeatureChangeEvaluation(
        artifact_id=feature_change_artifact.artifact_id,
        derived_state=derived_state,
        promotion=promotion,
        invalidation=invalidation,
        missing_requirements=tuple(dict.fromkeys(missing_requirements)),
        failing_invariants=tuple(dict.fromkeys(failing_invariants)),
        pending_invariants=tuple(dict.fromkeys(pending_invariants)),
    )


def _slot_bindings_from_payload(feature_change_artifact: CompositeArtifactRecord) -> FeatureChangeSlotBindings:
    raw = feature_change_artifact.payload.get("slot_bindings")
    if not isinstance(raw, Mapping):
        raise ValueError("feature_change.payload.slot_bindings is required for evaluation")
    return FeatureChangeSlotBindings.from_dict(raw)


def _verification_claims_from_payload(feature_change_artifact: CompositeArtifactRecord) -> tuple[VerificationClaimRecord, ...]:
    raw = feature_change_artifact.payload.get("verification_claims", [])
    if not isinstance(raw, list):
        raise TypeError("feature_change.payload.verification_claims must be a list")
    claims: list[VerificationClaimRecord] = []
    for index, item in enumerate(raw):
        if not isinstance(item, Mapping):
            raise TypeError(f"feature_change.payload.verification_claims[{index}] must be a mapping")
        claims.append(VerificationClaimRecord.from_dict(item))
    return tuple(claims)


def _test_categories(
    test_refs: Sequence[ArtifactRef],
    artifacts_by_id: Mapping[str, ArtifactRecord],
) -> set[str]:
    categories: set[str] = set()
    for ref in test_refs:
        artifact = artifacts_by_id.get(ref.artifact_id)
        if artifact is None:
            continue
        category = artifact.payload.get("category")
        if category is None:
            continue
        normalized = str(category).strip()
        if normalized:
            categories.add(normalized)
    return categories


def _iter_referenced_artifacts(
    feature_change_artifact: CompositeArtifactRecord,
    slot_bindings: FeatureChangeSlotBindings,
) -> Iterable[ArtifactRef]:
    seen: set[tuple[str, str, str | None]] = set()
    refs = [
        slot_bindings.spec.artifact,
        *slot_bindings.implementation_candidates.artifacts,
        *slot_bindings.tests.artifacts,
        *slot_bindings.approvals.artifacts,
        *slot_bindings.execution_receipts.artifacts,
        *feature_change_artifact.evidence_refs,
    ]
    if slot_bindings.selected_implementation is not None:
        refs.append(slot_bindings.selected_implementation.artifact)
    refs.extend(feature_change_artifact.child_artifacts)
    for ref in refs:
        key = (ref.artifact_id, ref.artifact_type, ref.revision)
        if key in seen:
            continue
        seen.add(key)
        yield ref


def _lineage_mismatch(feature_change_artifact: CompositeArtifactRecord, artifact: ArtifactRecord) -> bool:
    if feature_change_artifact.lineage is None or artifact.lineage is None:
        return False
    if feature_change_artifact.lineage.repo_id and artifact.lineage.repo_id:
        if feature_change_artifact.lineage.repo_id != artifact.lineage.repo_id:
            return True
    if feature_change_artifact.lineage.base_ref and artifact.lineage.base_ref:
        if feature_change_artifact.lineage.base_ref != artifact.lineage.base_ref:
            return True
    return False


def _claim_binds_current_inputs(
    claim: VerificationClaimRecord,
    *,
    spec_ref: ArtifactRef,
    selected_ref: ArtifactRef | None,
    test_refs: Sequence[ArtifactRef],
) -> bool:
    dependency_keys = {
        (ref.artifact_id, ref.artifact_type)
        for ref in claim.dependency_refs
    }
    required_keys = {
        (spec_ref.artifact_id, spec_ref.artifact_type),
    }
    if selected_ref is not None:
        required_keys.add((selected_ref.artifact_id, selected_ref.artifact_type))
    required_keys.update((ref.artifact_id, ref.artifact_type) for ref in test_refs)
    return required_keys.issubset(dependency_keys)


def _normalize_string_tuple(values: Sequence[str], field_name: str) -> tuple[str, ...]:
    if isinstance(values, (str, bytes, bytearray)):
        raise TypeError(f"{field_name} must be a sequence of str")
    normalized: list[str] = []
    for index, value in enumerate(values):
        if not isinstance(value, str):
            raise TypeError(f"{field_name}[{index}] must be str, got {type(value).__name__}")
        stripped = value.strip()
        if not stripped:
            raise ValueError(f"{field_name}[{index}] must be non-empty")
        normalized.append(stripped)
    return tuple(normalized)


def _normalize_ref_tuple(values: Sequence[ArtifactRef], field_name: str) -> tuple[ArtifactRef, ...]:
    normalized: list[ArtifactRef] = []
    for index, value in enumerate(values):
        if not isinstance(value, ArtifactRef):
            raise TypeError(f"{field_name}[{index}] must be ArtifactRef, got {type(value).__name__}")
        normalized.append(value)
    return tuple(normalized)


def _unique_refs(values: Sequence[ArtifactRef]) -> list[ArtifactRef]:
    seen: set[tuple[str, str, str | None]] = set()
    unique: list[ArtifactRef] = []
    for ref in values:
        key = (ref.artifact_id, ref.artifact_type, ref.revision)
        if key in seen:
            continue
        seen.add(key)
        unique.append(ref)
    return unique


def _require_string(value: str, field_name: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{field_name} is required")
    return normalized


__all__ = [
    "FeatureChangeEvaluation",
    "FeatureChangePolicy",
    "INVALIDATION_STATUS_FRESH",
    "INVALIDATION_STATUS_INVALID",
    "INVALIDATION_STATUS_STALE",
    "InvalidationRecord",
    "PromotionDecision",
    "evaluate_feature_change_artifact",
    "evaluate_feature_task_projection",
]
