from __future__ import annotations

from collections.abc import Iterable, Mapping
import hashlib
import json

from .artifact_evaluator import FeatureChangeEvaluation
from .artifact_projection import FeatureTaskArtifactProjection
from .artifacts import ArtifactRef
from .dsl import (
    CompiledObligation,
    InputContract,
    MaterializedInputSet,
    ObligationIntent,
    ObligationSpec,
    ProducedArtifactSpec,
    ProtocolSpec,
    RefSelector,
)


FEATURE_CHANGE_ARTIFACT_TYPE = "feature_change"

OBLIGATION_SPEC_BIND_IMPLEMENTATION_CANDIDATES = "bind_implementation_candidates"
OBLIGATION_SPEC_SELECT_IMPLEMENTATION = "select_implementation"
OBLIGATION_SPEC_RESELECT_IMPLEMENTATION = "reselect_implementation"
OBLIGATION_SPEC_BIND_REQUIRED_TESTS = "bind_required_tests"
OBLIGATION_SPEC_VERIFY_LOCAL_FEATURE = "verify_local_feature"
OBLIGATION_SPEC_VERIFY_CROSS_FEATURE = "verify_cross_feature"
OBLIGATION_SPEC_VERIFY_COMPOSITE_FEATURE = "verify_composite_feature"
OBLIGATION_SPEC_REVERIFY_REQUIRED_CLAIMS = "reverify_required_claims"
OBLIGATION_SPEC_COLLECT_APPROVALS = "collect_approvals"
OBLIGATION_SPEC_RECOMPOSE_FEATURE_CHANGE = "recompose_feature_change"
OBLIGATION_SPEC_REPLACE_INVALID_INPUTS = "replace_invalid_inputs"
OBLIGATION_SPEC_REVERIFY_STALE_INPUTS = "reverify_stale_inputs"

_ACTION_TO_SPEC_ID = {
    "bind_implementation_candidates": OBLIGATION_SPEC_BIND_IMPLEMENTATION_CANDIDATES,
    "select_implementation": OBLIGATION_SPEC_SELECT_IMPLEMENTATION,
    "reselect_implementation": OBLIGATION_SPEC_RESELECT_IMPLEMENTATION,
    "bind_required_tests": OBLIGATION_SPEC_BIND_REQUIRED_TESTS,
    "verify_required_claims": OBLIGATION_SPEC_VERIFY_COMPOSITE_FEATURE,
    "reverify_required_claims": OBLIGATION_SPEC_REVERIFY_REQUIRED_CLAIMS,
    "collect_approvals": OBLIGATION_SPEC_COLLECT_APPROVALS,
    "recompose_feature_change": OBLIGATION_SPEC_RECOMPOSE_FEATURE_CHANGE,
    "replace_invalid_inputs": OBLIGATION_SPEC_REPLACE_INVALID_INPUTS,
    "reverify_stale_inputs": OBLIGATION_SPEC_REVERIFY_STALE_INPUTS,
}

_VERIFICATION_SCOPE_TO_SPEC_ID = {
    "local": OBLIGATION_SPEC_VERIFY_LOCAL_FEATURE,
    "cross": OBLIGATION_SPEC_VERIFY_CROSS_FEATURE,
    "composite": OBLIGATION_SPEC_VERIFY_COMPOSITE_FEATURE,
}

_VERIFICATION_SCOPE_ORDER = ("local", "cross", "composite")


def default_feature_change_protocol_spec() -> ProtocolSpec:
    return ProtocolSpec(
        artifact_type=FEATURE_CHANGE_ARTIFACT_TYPE,
        slots=(
            "spec",
            "implementation_candidates",
            "selected_implementation",
            "test_obligations",
            "verification_claims",
            "approvals",
            "execution_receipts",
        ),
        invariants=(
            "same_feature_id",
            "selected_implementation_is_candidate",
            "claims_bind_current_inputs",
        ),
        required_claim_scopes=("local", "cross", "composite"),
        obligations=(
            _obligation_spec(
                id=OBLIGATION_SPEC_BIND_IMPLEMENTATION_CANDIDATES,
                obligation_kind="composition",
                required=("slot://spec",),
                produces=(ProducedArtifactSpec("implementation_candidate"),),
            ),
            _obligation_spec(
                id=OBLIGATION_SPEC_SELECT_IMPLEMENTATION,
                obligation_kind="composition",
                required=("slot://implementation_candidates",),
                produces=(ProducedArtifactSpec("slot_binding", claim="selected_implementation"),),
            ),
            _obligation_spec(
                id=OBLIGATION_SPEC_RESELECT_IMPLEMENTATION,
                obligation_kind="composition",
                required=("slot://implementation_candidates", "slot://selected_implementation"),
                produces=(ProducedArtifactSpec("slot_binding", claim="selected_implementation"),),
            ),
            _obligation_spec(
                id=OBLIGATION_SPEC_BIND_REQUIRED_TESTS,
                obligation_kind="composition",
                required=("slot://spec#acceptance_criteria",),
                optional=("slot://selected_implementation",),
                produces=(ProducedArtifactSpec("test_obligation"),),
            ),
            _obligation_spec(
                id=OBLIGATION_SPEC_VERIFY_LOCAL_FEATURE,
                obligation_kind="verification",
                required=(
                    "slot://spec#acceptance_criteria",
                    "slot://test_obligations",
                ),
                optional=("slot://execution_receipts/*",),
                forbidden=("external://unrelated_prior_outputs/*",),
                produces=(
                    ProducedArtifactSpec(
                        "verification_claim",
                        claim="local_spec_and_tests_satisfied",
                        scope="local",
                    ),
                ),
                execution_policy_ref="witness_default",
            ),
            _obligation_spec(
                id=OBLIGATION_SPEC_VERIFY_CROSS_FEATURE,
                obligation_kind="verification",
                required=(
                    "slot://spec#acceptance_criteria",
                    "slot://selected_implementation",
                ),
                optional=("slot://execution_receipts/*",),
                forbidden=("external://unrelated_prior_outputs/*",),
                produces=(
                    ProducedArtifactSpec(
                        "verification_claim",
                        claim="selected_implementation_binds_spec",
                        scope="cross",
                    ),
                ),
                execution_policy_ref="witness_default",
            ),
            _obligation_spec(
                id=OBLIGATION_SPEC_VERIFY_COMPOSITE_FEATURE,
                obligation_kind="verification",
                required=(
                    "slot://spec#acceptance_criteria",
                    "slot://selected_implementation",
                    "slot://test_obligations",
                ),
                optional=("slot://execution_receipts/*",),
                forbidden=("external://unrelated_prior_outputs/*",),
                produces=(
                    ProducedArtifactSpec(
                        "verification_claim",
                        claim="acceptance_criteria_satisfied",
                        scope="composite",
                    ),
                ),
                execution_policy_ref="witness_default",
            ),
            _obligation_spec(
                id=OBLIGATION_SPEC_REVERIFY_REQUIRED_CLAIMS,
                obligation_kind="verification",
                required=(
                    "slot://spec#acceptance_criteria",
                    "slot://selected_implementation",
                    "slot://test_obligations",
                ),
                optional=("slot://verification_claims", "slot://execution_receipts/*"),
                produces=(ProducedArtifactSpec("verification_claim", scope="composite"),),
                execution_policy_ref="witness_default",
            ),
            _obligation_spec(
                id=OBLIGATION_SPEC_COLLECT_APPROVALS,
                obligation_kind="approval",
                required=("slot://spec", "slot://selected_implementation"),
                produces=(ProducedArtifactSpec("approval"),),
            ),
            _obligation_spec(
                id=OBLIGATION_SPEC_RECOMPOSE_FEATURE_CHANGE,
                obligation_kind="composition",
                required=("slot://spec", "slot://selected_implementation"),
                optional=("slot://test_obligations", "slot://verification_claims", "slot://execution_receipts/*"),
                produces=(ProducedArtifactSpec("feature_change"),),
            ),
            _obligation_spec(
                id=OBLIGATION_SPEC_REPLACE_INVALID_INPUTS,
                obligation_kind="invalidation_repair",
                required=("slot://spec", "slot://selected_implementation"),
                optional=("slot://test_obligations",),
                produces=(ProducedArtifactSpec("feature_change"),),
            ),
            _obligation_spec(
                id=OBLIGATION_SPEC_REVERIFY_STALE_INPUTS,
                obligation_kind="verification",
                required=("slot://spec", "slot://selected_implementation"),
                optional=("slot://test_obligations", "slot://verification_claims", "slot://execution_receipts/*"),
                produces=(ProducedArtifactSpec("verification_claim"),),
                execution_policy_ref="witness_default",
            ),
        ),
    )


def feature_change_obligation_specs_by_id(
    protocol: ProtocolSpec | None = None,
) -> dict[str, ObligationSpec]:
    resolved = protocol or default_feature_change_protocol_spec()
    return {obligation.id: obligation for obligation in resolved.obligations}


def obligation_intents_from_feature_change_evaluation(
    evaluation: FeatureChangeEvaluation,
) -> tuple[ObligationIntent, ...]:
    return evaluation.obligation_intents


def compile_feature_change_obligation(
    intent: ObligationIntent,
    projection: FeatureTaskArtifactProjection,
    *,
    protocol: ProtocolSpec | None = None,
) -> CompiledObligation:
    spec_id = _spec_ids_for_intent(intent)[0]
    return _compile_feature_change_obligation_for_spec_id(intent, projection, spec_id, protocol=protocol)


def _compile_feature_change_obligation_for_spec_id(
    intent: ObligationIntent,
    projection: FeatureTaskArtifactProjection,
    spec_id: str,
    *,
    protocol: ProtocolSpec | None = None,
) -> CompiledObligation:
    specs = feature_change_obligation_specs_by_id(protocol)
    spec = specs[spec_id]
    bound_inputs = tuple(_bind_input_contract(spec.input_contract, projection))
    materialized_input_set = MaterializedInputSet(
        refs=bound_inputs,
        fingerprint=fingerprint_materialized_inputs(bound_inputs),
    )
    return CompiledObligation(
        id=f"obligation-{projection.feature_change_artifact.artifact_id}-{spec.id}",
        spec_ref=spec.id,
        target_artifact=intent.target_artifact,
        bound_inputs=bound_inputs,
        materialized_input_set=materialized_input_set,
        execution_policy_ref=spec.execution_policy_ref,
    )


def compile_feature_change_obligations(
    intents: Iterable[ObligationIntent],
    projection: FeatureTaskArtifactProjection,
    *,
    protocol: ProtocolSpec | None = None,
) -> tuple[CompiledObligation, ...]:
    obligations: list[CompiledObligation] = []
    for intent in intents:
        obligations.extend(
            _compile_feature_change_obligation_for_spec_id(intent, projection, spec_id, protocol=protocol)
            for spec_id in _spec_ids_for_intent(intent)
        )
    return tuple(obligations)


def _spec_ids_for_intent(intent: ObligationIntent) -> tuple[str, ...]:
    if intent.intent_kind in {"verify_required_claims", "reverify_required_claims"}:
        scopes = _ordered_verification_scopes(intent.missing_scopes or _VERIFICATION_SCOPE_ORDER)
        return tuple(_VERIFICATION_SCOPE_TO_SPEC_ID[scope] for scope in scopes)
    spec_id = _ACTION_TO_SPEC_ID.get(intent.intent_kind)
    if spec_id is None:
        raise ValueError(f"unsupported feature change obligation intent: {intent.intent_kind}")
    return (spec_id,)


def _ordered_verification_scopes(scopes: Iterable[str]) -> tuple[str, ...]:
    normalized = tuple(dict.fromkeys(str(scope).strip() for scope in scopes if str(scope).strip()))
    unknown = [scope for scope in normalized if scope not in _VERIFICATION_SCOPE_TO_SPEC_ID]
    if unknown:
        raise ValueError(f"unsupported verification claim scopes: {', '.join(unknown)}")
    scope_set = set(normalized)
    return tuple(scope for scope in _VERIFICATION_SCOPE_ORDER if scope in scope_set)


def fingerprint_materialized_inputs(refs: Iterable[str]) -> str:
    payload = json.dumps(list(refs), separators=(",", ":"), ensure_ascii=True)
    return f"sha256:{hashlib.sha256(payload.encode('utf-8')).hexdigest()}"


def _obligation_spec(
    *,
    id: str,
    obligation_kind: str,
    required: tuple[str, ...],
    optional: tuple[str, ...] = (),
    forbidden: tuple[str, ...] = (),
    produces: tuple[ProducedArtifactSpec, ...],
    execution_policy_ref: str | None = None,
) -> ObligationSpec:
    return ObligationSpec(
        id=id,
        obligation_kind=obligation_kind,
        input_contract=InputContract(
            required=tuple(RefSelector(ref) for ref in required),
            optional=tuple(RefSelector(ref) for ref in optional),
            forbidden=tuple(RefSelector(ref) for ref in forbidden),
            closure={
                "dependency_rule": "current_bound_slots_only",
                "stale_on": [
                    "spec_revision_changed",
                    "selected_implementation_changed",
                    "test_obligation_changed",
                ],
            },
        ),
        produces=produces,
        execution_policy_ref=execution_policy_ref,
    )


def _bind_input_contract(
    input_contract: InputContract,
    projection: FeatureTaskArtifactProjection,
) -> Iterable[str]:
    for selector in (*input_contract.required, *input_contract.optional):
        yield from _bind_slot_selector(selector.ref, projection)


def _bind_slot_selector(
    selector: str,
    projection: FeatureTaskArtifactProjection,
) -> tuple[str, ...]:
    scheme, remainder = selector.split("://", 1)
    if scheme != "slot":
        return ()
    slot_name, fragment = _split_fragment(remainder)
    wildcard = slot_name.endswith("/*")
    if wildcard:
        slot_name = slot_name[:-2]
    refs = _slot_refs(slot_name, projection)
    if not refs:
        return ()
    if not wildcard and len(refs) > 1:
        return tuple(_artifact_uri(ref.artifact_id, fragment=fragment) for ref in refs)
    return tuple(_artifact_uri(ref.artifact_id, fragment=fragment) for ref in refs)


def _slot_refs(slot_name: str, projection: FeatureTaskArtifactProjection) -> tuple[ArtifactRef, ...]:
    bindings = projection.slot_bindings
    if slot_name == "spec":
        return (bindings.spec.artifact,)
    if slot_name == "implementation_candidates":
        return bindings.implementation_candidates.artifacts
    if slot_name == "selected_implementation":
        if bindings.selected_implementation is None:
            return ()
        return (bindings.selected_implementation.artifact,)
    if slot_name in {"test_obligations", "tests"}:
        return bindings.tests.artifacts
    if slot_name == "verification_claims":
        return bindings.verification_claims.artifacts
    if slot_name == "approvals":
        return bindings.approvals.artifacts
    if slot_name == "execution_receipts":
        return bindings.execution_receipts.artifacts
    raise ValueError(f"unsupported feature change slot selector: slot://{slot_name}")


def _split_fragment(value: str) -> tuple[str, str | None]:
    if "#" not in value:
        return value, None
    base, fragment = value.split("#", 1)
    return base, fragment or None


def _artifact_uri(artifact_id: str, *, fragment: str | None = None) -> str:
    uri = f"artifact://{artifact_id}"
    if fragment:
        uri = f"{uri}#{fragment}"
    return uri


__all__ = [
    "FEATURE_CHANGE_ARTIFACT_TYPE",
    "OBLIGATION_SPEC_BIND_IMPLEMENTATION_CANDIDATES",
    "OBLIGATION_SPEC_BIND_REQUIRED_TESTS",
    "OBLIGATION_SPEC_COLLECT_APPROVALS",
    "OBLIGATION_SPEC_RECOMPOSE_FEATURE_CHANGE",
    "OBLIGATION_SPEC_REPLACE_INVALID_INPUTS",
    "OBLIGATION_SPEC_RESELECT_IMPLEMENTATION",
    "OBLIGATION_SPEC_REVERIFY_REQUIRED_CLAIMS",
    "OBLIGATION_SPEC_REVERIFY_STALE_INPUTS",
    "OBLIGATION_SPEC_SELECT_IMPLEMENTATION",
    "OBLIGATION_SPEC_VERIFY_CROSS_FEATURE",
    "OBLIGATION_SPEC_VERIFY_COMPOSITE_FEATURE",
    "OBLIGATION_SPEC_VERIFY_LOCAL_FEATURE",
    "compile_feature_change_obligation",
    "compile_feature_change_obligations",
    "default_feature_change_protocol_spec",
    "feature_change_obligation_specs_by_id",
    "fingerprint_materialized_inputs",
    "obligation_intents_from_feature_change_evaluation",
]
