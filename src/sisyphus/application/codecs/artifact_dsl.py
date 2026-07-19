from __future__ import annotations

from collections.abc import Mapping

from ...domain.artifact.dsl import (
    COMPILED_OBLIGATION_KIND,
    DSL_SCHEMA_VERSION,
    EXECUTION_POLICY_KIND,
    INPUT_CONTRACT_KIND,
    INPUT_MODE_FORBIDDEN,
    INPUT_MODE_OPTIONAL,
    INPUT_MODE_REQUIRED,
    MATERIALIZED_INPUT_SET_KIND,
    OBLIGATION_INTENT_KIND,
    OBLIGATION_SPEC_KIND,
    PROTOCOL_SPEC_KIND,
    CompiledObligation,
    ExecutionPolicy,
    InputContract,
    MaterializedInputSet,
    ObligationIntent,
    ObligationSpec,
    ProducedArtifactSpec,
    ProtocolSpec,
    RefSelector,
)
from .json_records import (
    decode_mapping_tuple,
    decode_ref_tuple,
    decode_string_tuple,
    normalize_json_mapping,
    optional_int,
    optional_string,
    reject_unknown_fields,
    require_list,
    require_mapping,
    require_string,
)


_REF_SELECTOR_FIELDS = frozenset({"ref", "mode", "reason"})
_INPUT_CONTRACT_FIELDS = frozenset(
    {"schema_version", "kind", "required", "optional", "forbidden", "closure"}
)
_PRODUCED_ARTIFACT_FIELDS = frozenset({"artifact_type", "claim", "scope"})
_OBLIGATION_SPEC_FIELDS = frozenset(
    {
        "schema_version",
        "kind",
        "id",
        "obligation_kind",
        "input_contract",
        "produces",
        "execution_policy_ref",
    }
)
_PROTOCOL_SPEC_FIELDS = frozenset(
    {
        "schema_version",
        "kind",
        "artifact_type",
        "slots",
        "invariants",
        "required_claim_scopes",
        "obligations",
    }
)
_EXECUTION_POLICY_FIELDS = frozenset(
    {
        "schema_version",
        "kind",
        "id",
        "runner",
        "role",
        "provider",
        "model",
        "tool",
        "timeout_seconds",
        "retry",
        "budget",
    }
)
_OBLIGATION_INTENT_FIELDS = frozenset(
    {
        "schema_version",
        "kind",
        "intent_kind",
        "target_artifact",
        "missing_scopes",
        "reasons",
        "data",
    }
)
_MATERIALIZED_INPUT_SET_FIELDS = frozenset(
    {"schema_version", "kind", "refs", "fingerprint"}
)
_COMPILED_OBLIGATION_FIELDS = frozenset(
    {
        "schema_version",
        "kind",
        "id",
        "spec_ref",
        "target_artifact",
        "bound_inputs",
        "materialized_input_set",
        "execution_policy_ref",
        "status",
    }
)


def encode_ref_selector(value: RefSelector) -> dict[str, object]:
    data: dict[str, object] = {"ref": value.ref, "mode": value.mode}
    if value.reason is not None:
        data["reason"] = value.reason
    return data


def decode_ref_selector(raw: Mapping[str, object]) -> RefSelector:
    mapping = require_mapping(raw, "ref_selector")
    reject_unknown_fields(mapping, _REF_SELECTOR_FIELDS, "ref_selector")
    return RefSelector(
        ref=require_string(mapping.get("ref"), "ref_selector.ref"),
        mode=optional_string(mapping.get("mode")) or INPUT_MODE_REQUIRED,
        reason=optional_string(mapping.get("reason")),
    )


def encode_input_contract(value: InputContract) -> dict[str, object]:
    return {
        "schema_version": value.schema_version,
        "kind": value.kind,
        "required": [encode_ref_selector(item) for item in value.required],
        "optional": [encode_ref_selector(item) for item in value.optional],
        "forbidden": [encode_ref_selector(item) for item in value.forbidden],
        "closure": dict(value.closure),
    }


def decode_input_contract(raw: Mapping[str, object]) -> InputContract:
    mapping = _validate_record(raw, _INPUT_CONTRACT_FIELDS, INPUT_CONTRACT_KIND, "input_contract")
    return InputContract(
        required=_decode_selectors(
            mapping.get("required", []), INPUT_MODE_REQUIRED, "input_contract.required"
        ),
        optional=_decode_selectors(
            mapping.get("optional", []), INPUT_MODE_OPTIONAL, "input_contract.optional"
        ),
        forbidden=_decode_selectors(
            mapping.get("forbidden", []), INPUT_MODE_FORBIDDEN, "input_contract.forbidden"
        ),
        closure=normalize_json_mapping(mapping.get("closure", {}), "input_contract.closure"),
    )


def encode_produced_artifact(value: ProducedArtifactSpec) -> dict[str, object]:
    data: dict[str, object] = {"artifact_type": value.artifact_type}
    if value.claim is not None:
        data["claim"] = value.claim
    if value.scope is not None:
        data["scope"] = value.scope
    return data


def decode_produced_artifact(raw: Mapping[str, object]) -> ProducedArtifactSpec:
    mapping = require_mapping(raw, "produced_artifact")
    reject_unknown_fields(mapping, _PRODUCED_ARTIFACT_FIELDS, "produced_artifact")
    return ProducedArtifactSpec(
        artifact_type=require_string(
            mapping.get("artifact_type"), "produced_artifact.artifact_type"
        ),
        claim=optional_string(mapping.get("claim")),
        scope=optional_string(mapping.get("scope")),
    )


def encode_obligation_spec(value: ObligationSpec) -> dict[str, object]:
    data: dict[str, object] = {
        "schema_version": value.schema_version,
        "kind": value.kind,
        "id": value.id,
        "obligation_kind": value.obligation_kind,
        "input_contract": encode_input_contract(value.input_contract),
        "produces": [encode_produced_artifact(item) for item in value.produces],
    }
    if value.execution_policy_ref is not None:
        data["execution_policy_ref"] = value.execution_policy_ref
    return data


def decode_obligation_spec(raw: Mapping[str, object]) -> ObligationSpec:
    mapping = _validate_record(raw, _OBLIGATION_SPEC_FIELDS, OBLIGATION_SPEC_KIND, "obligation_spec")
    return ObligationSpec(
        id=require_string(mapping.get("id"), "obligation_spec.id"),
        obligation_kind=require_string(
            mapping.get("obligation_kind"), "obligation_spec.obligation_kind"
        ),
        input_contract=decode_input_contract(
            require_mapping(mapping.get("input_contract"), "obligation_spec.input_contract")
        ),
        produces=decode_mapping_tuple(
            mapping.get("produces", []), decode_produced_artifact, "obligation_spec.produces"
        ),
        execution_policy_ref=optional_string(mapping.get("execution_policy_ref")),
    )


def encode_protocol_spec(value: ProtocolSpec) -> dict[str, object]:
    return {
        "schema_version": value.schema_version,
        "kind": value.kind,
        "artifact_type": value.artifact_type,
        "slots": list(value.slots),
        "invariants": list(value.invariants),
        "required_claim_scopes": list(value.required_claim_scopes),
        "obligations": [encode_obligation_spec(item) for item in value.obligations],
    }


def decode_protocol_spec(raw: Mapping[str, object]) -> ProtocolSpec:
    mapping = _validate_record(raw, _PROTOCOL_SPEC_FIELDS, PROTOCOL_SPEC_KIND, "protocol_spec")
    return ProtocolSpec(
        artifact_type=require_string(mapping.get("artifact_type"), "protocol_spec.artifact_type"),
        slots=decode_string_tuple(mapping.get("slots", []), "protocol_spec.slots"),
        invariants=decode_string_tuple(mapping.get("invariants", []), "protocol_spec.invariants"),
        required_claim_scopes=decode_string_tuple(
            mapping.get("required_claim_scopes", []), "protocol_spec.required_claim_scopes"
        ),
        obligations=decode_mapping_tuple(
            mapping.get("obligations", []), decode_obligation_spec, "protocol_spec.obligations"
        ),
    )


def encode_execution_policy(value: ExecutionPolicy) -> dict[str, object]:
    data: dict[str, object] = {
        "schema_version": value.schema_version,
        "kind": value.kind,
        "id": value.id,
        "runner": value.runner,
        "retry": value.retry,
        "budget": dict(value.budget),
    }
    for key in ("role", "provider", "model", "tool", "timeout_seconds"):
        item = getattr(value, key)
        if item is not None:
            data[key] = item
    return data


def decode_execution_policy(raw: Mapping[str, object]) -> ExecutionPolicy:
    mapping = _validate_record(
        raw, _EXECUTION_POLICY_FIELDS, EXECUTION_POLICY_KIND, "execution_policy"
    )
    return ExecutionPolicy(
        id=require_string(mapping.get("id"), "execution_policy.id"),
        runner=require_string(mapping.get("runner"), "execution_policy.runner"),
        role=optional_string(mapping.get("role")),
        provider=optional_string(mapping.get("provider")),
        model=optional_string(mapping.get("model")),
        tool=optional_string(mapping.get("tool")),
        timeout_seconds=optional_int(
            mapping.get("timeout_seconds"), "execution_policy.timeout_seconds"
        ),
        retry=optional_int(mapping.get("retry"), "execution_policy.retry") or 0,
        budget=normalize_json_mapping(mapping.get("budget", {}), "execution_policy.budget"),
    )


def encode_obligation_intent(value: ObligationIntent) -> dict[str, object]:
    return {
        "schema_version": value.schema_version,
        "kind": value.kind,
        "intent_kind": value.intent_kind,
        "target_artifact": value.target_artifact,
        "missing_scopes": list(value.missing_scopes),
        "reasons": list(value.reasons),
        "data": dict(value.data),
    }


def decode_obligation_intent(raw: Mapping[str, object]) -> ObligationIntent:
    mapping = _validate_record(
        raw, _OBLIGATION_INTENT_FIELDS, OBLIGATION_INTENT_KIND, "obligation_intent"
    )
    return ObligationIntent(
        intent_kind=require_string(mapping.get("intent_kind"), "obligation_intent.intent_kind"),
        target_artifact=require_string(
            mapping.get("target_artifact"), "obligation_intent.target_artifact"
        ),
        missing_scopes=decode_string_tuple(
            mapping.get("missing_scopes", []), "obligation_intent.missing_scopes"
        ),
        reasons=decode_string_tuple(mapping.get("reasons", []), "obligation_intent.reasons"),
        data=normalize_json_mapping(mapping.get("data", {}), "obligation_intent.data"),
    )


def encode_materialized_input_set(value: MaterializedInputSet) -> dict[str, object]:
    return {
        "schema_version": value.schema_version,
        "kind": value.kind,
        "refs": list(value.refs),
        "fingerprint": value.fingerprint,
    }


def decode_materialized_input_set(raw: Mapping[str, object]) -> MaterializedInputSet:
    mapping = _validate_record(
        raw,
        _MATERIALIZED_INPUT_SET_FIELDS,
        MATERIALIZED_INPUT_SET_KIND,
        "materialized_input_set",
    )
    return MaterializedInputSet(
        refs=decode_ref_tuple(mapping.get("refs", []), "materialized_input_set.refs"),
        fingerprint=require_string(
            mapping.get("fingerprint"), "materialized_input_set.fingerprint"
        ),
    )


def encode_compiled_obligation(value: CompiledObligation) -> dict[str, object]:
    data: dict[str, object] = {
        "schema_version": value.schema_version,
        "kind": value.kind,
        "id": value.id,
        "spec_ref": value.spec_ref,
        "target_artifact": value.target_artifact,
        "bound_inputs": list(value.bound_inputs),
        "materialized_input_set": encode_materialized_input_set(value.materialized_input_set),
        "status": value.status,
    }
    if value.execution_policy_ref is not None:
        data["execution_policy_ref"] = value.execution_policy_ref
    return data


def decode_compiled_obligation(raw: Mapping[str, object]) -> CompiledObligation:
    mapping = _validate_record(
        raw,
        _COMPILED_OBLIGATION_FIELDS,
        COMPILED_OBLIGATION_KIND,
        "compiled_obligation",
    )
    return CompiledObligation(
        id=require_string(mapping.get("id"), "compiled_obligation.id"),
        spec_ref=require_string(mapping.get("spec_ref"), "compiled_obligation.spec_ref"),
        target_artifact=require_string(
            mapping.get("target_artifact"), "compiled_obligation.target_artifact"
        ),
        bound_inputs=decode_ref_tuple(
            mapping.get("bound_inputs", []), "compiled_obligation.bound_inputs"
        ),
        materialized_input_set=decode_materialized_input_set(
            require_mapping(
                mapping.get("materialized_input_set"),
                "compiled_obligation.materialized_input_set",
            )
        ),
        execution_policy_ref=optional_string(mapping.get("execution_policy_ref")),
        status=optional_string(mapping.get("status")) or "pending",
    )


def _decode_selectors(value: object, mode: str, field_name: str) -> tuple[RefSelector, ...]:
    items = require_list(value, field_name)
    selectors: list[RefSelector] = []
    for index, item in enumerate(items):
        selector = decode_ref_selector(require_mapping(item, f"{field_name}[{index}]"))
        if selector.mode != mode:
            selector = RefSelector(ref=selector.ref, mode=mode, reason=selector.reason)
        selectors.append(selector)
    return tuple(selectors)


def _validate_record(
    raw: Mapping[str, object],
    allowed_fields: frozenset[str],
    expected_kind: str,
    field_name: str,
) -> Mapping[str, object]:
    mapping = require_mapping(raw, field_name)
    reject_unknown_fields(mapping, allowed_fields, field_name)
    schema_version = optional_string(mapping.get("schema_version"))
    if schema_version not in (None, DSL_SCHEMA_VERSION):
        raise ValueError(
            f"{field_name}.schema_version must be {DSL_SCHEMA_VERSION!r}, got {schema_version!r}"
        )
    kind = optional_string(mapping.get("kind")) or expected_kind
    if kind != expected_kind:
        raise ValueError(f"{field_name}.kind must be {expected_kind!r}, got {kind!r}")
    return mapping


__all__ = [
    "decode_compiled_obligation",
    "decode_execution_policy",
    "decode_input_contract",
    "decode_materialized_input_set",
    "decode_obligation_intent",
    "decode_obligation_spec",
    "decode_produced_artifact",
    "decode_protocol_spec",
    "decode_ref_selector",
    "encode_compiled_obligation",
    "encode_execution_policy",
    "encode_input_contract",
    "encode_materialized_input_set",
    "encode_obligation_intent",
    "encode_obligation_spec",
    "encode_produced_artifact",
    "encode_protocol_spec",
    "encode_ref_selector",
]
