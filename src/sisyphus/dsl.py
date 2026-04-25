from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field

from .utils import find_unknown_fields


DSL_SCHEMA_VERSION = "sisyphus.dsl.v1"

PROTOCOL_SPEC_KIND = "protocol_spec"
OBLIGATION_SPEC_KIND = "obligation_spec"
INPUT_CONTRACT_KIND = "input_contract"
EXECUTION_POLICY_KIND = "execution_policy"
OBLIGATION_INTENT_KIND = "obligation_intent"
COMPILED_OBLIGATION_KIND = "compiled_obligation"
MATERIALIZED_INPUT_SET_KIND = "materialized_input_set"

INPUT_MODE_REQUIRED = "required"
INPUT_MODE_OPTIONAL = "optional"
INPUT_MODE_FORBIDDEN = "forbidden"


_REF_SELECTOR_FIELDS = frozenset({"ref", "mode", "reason"})
_INPUT_CONTRACT_FIELDS = frozenset(
    {
        "schema_version",
        "kind",
        "required",
        "optional",
        "forbidden",
        "closure",
    }
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
    {
        "schema_version",
        "kind",
        "refs",
        "fingerprint",
    }
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


@dataclass(frozen=True, slots=True)
class RefSelector:
    ref: str
    mode: str = INPUT_MODE_REQUIRED
    reason: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "ref", _require_ref(self.ref, "ref"))
        object.__setattr__(self, "mode", _require_one_of(self.mode, "mode", _INPUT_MODES))
        object.__setattr__(self, "reason", _optional_string(self.reason))

    def to_dict(self) -> dict[str, object]:
        data: dict[str, object] = {"ref": self.ref, "mode": self.mode}
        if self.reason is not None:
            data["reason"] = self.reason
        return data

    @classmethod
    def from_dict(cls, raw: Mapping[str, object]) -> RefSelector:
        mapping = _require_mapping(raw, "ref_selector")
        _raise_unknown_fields(mapping, _REF_SELECTOR_FIELDS, "ref_selector")
        return cls(
            ref=_require_string(mapping.get("ref"), "ref_selector.ref"),
            mode=_optional_string(mapping.get("mode")) or INPUT_MODE_REQUIRED,
            reason=_optional_string(mapping.get("reason")),
        )


@dataclass(frozen=True, slots=True)
class InputContract:
    required: tuple[RefSelector, ...] = ()
    optional: tuple[RefSelector, ...] = ()
    forbidden: tuple[RefSelector, ...] = ()
    closure: Mapping[str, object] = field(default_factory=dict)

    schema_version: str = field(init=False, default=DSL_SCHEMA_VERSION)
    kind: str = field(init=False, default=INPUT_CONTRACT_KIND)

    def __post_init__(self) -> None:
        object.__setattr__(self, "required", _coerce_selectors(self.required, INPUT_MODE_REQUIRED, "required"))
        object.__setattr__(self, "optional", _coerce_selectors(self.optional, INPUT_MODE_OPTIONAL, "optional"))
        object.__setattr__(self, "forbidden", _coerce_selectors(self.forbidden, INPUT_MODE_FORBIDDEN, "forbidden"))
        object.__setattr__(self, "closure", _normalize_json_mapping(self.closure, "closure"))

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "kind": self.kind,
            "required": [selector.to_dict() for selector in self.required],
            "optional": [selector.to_dict() for selector in self.optional],
            "forbidden": [selector.to_dict() for selector in self.forbidden],
            "closure": dict(self.closure),
        }

    @classmethod
    def from_dict(cls, raw: Mapping[str, object]) -> InputContract:
        mapping = _validate_record(raw, _INPUT_CONTRACT_FIELDS, INPUT_CONTRACT_KIND, "input_contract")
        return cls(
            required=_load_selectors(mapping.get("required", []), INPUT_MODE_REQUIRED, "input_contract.required"),
            optional=_load_selectors(mapping.get("optional", []), INPUT_MODE_OPTIONAL, "input_contract.optional"),
            forbidden=_load_selectors(mapping.get("forbidden", []), INPUT_MODE_FORBIDDEN, "input_contract.forbidden"),
            closure=_normalize_json_mapping(mapping.get("closure", {}), "input_contract.closure"),
        )


@dataclass(frozen=True, slots=True)
class ProducedArtifactSpec:
    artifact_type: str
    claim: str | None = None
    scope: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "artifact_type", _require_string(self.artifact_type, "artifact_type"))
        object.__setattr__(self, "claim", _optional_string(self.claim))
        object.__setattr__(self, "scope", _optional_string(self.scope))

    def to_dict(self) -> dict[str, object]:
        data: dict[str, object] = {"artifact_type": self.artifact_type}
        if self.claim is not None:
            data["claim"] = self.claim
        if self.scope is not None:
            data["scope"] = self.scope
        return data

    @classmethod
    def from_dict(cls, raw: Mapping[str, object]) -> ProducedArtifactSpec:
        mapping = _require_mapping(raw, "produced_artifact")
        _raise_unknown_fields(mapping, _PRODUCED_ARTIFACT_FIELDS, "produced_artifact")
        return cls(
            artifact_type=_require_string(mapping.get("artifact_type"), "produced_artifact.artifact_type"),
            claim=_optional_string(mapping.get("claim")),
            scope=_optional_string(mapping.get("scope")),
        )


@dataclass(frozen=True, slots=True)
class ObligationSpec:
    id: str
    obligation_kind: str
    input_contract: InputContract
    produces: tuple[ProducedArtifactSpec, ...] = ()
    execution_policy_ref: str | None = None

    schema_version: str = field(init=False, default=DSL_SCHEMA_VERSION)
    kind: str = field(init=False, default=OBLIGATION_SPEC_KIND)

    def __post_init__(self) -> None:
        object.__setattr__(self, "id", _require_string(self.id, "id"))
        object.__setattr__(self, "obligation_kind", _require_string(self.obligation_kind, "obligation_kind"))
        if not isinstance(self.input_contract, InputContract):
            raise TypeError("input_contract must be InputContract")
        object.__setattr__(self, "produces", _coerce_tuple(self.produces, ProducedArtifactSpec, "produces"))
        object.__setattr__(self, "execution_policy_ref", _optional_string(self.execution_policy_ref))

    def to_dict(self) -> dict[str, object]:
        data: dict[str, object] = {
            "schema_version": self.schema_version,
            "kind": self.kind,
            "id": self.id,
            "obligation_kind": self.obligation_kind,
            "input_contract": self.input_contract.to_dict(),
            "produces": [artifact.to_dict() for artifact in self.produces],
        }
        if self.execution_policy_ref is not None:
            data["execution_policy_ref"] = self.execution_policy_ref
        return data

    @classmethod
    def from_dict(cls, raw: Mapping[str, object]) -> ObligationSpec:
        mapping = _validate_record(raw, _OBLIGATION_SPEC_FIELDS, OBLIGATION_SPEC_KIND, "obligation_spec")
        return cls(
            id=_require_string(mapping.get("id"), "obligation_spec.id"),
            obligation_kind=_require_string(mapping.get("obligation_kind"), "obligation_spec.obligation_kind"),
            input_contract=InputContract.from_dict(
                _require_mapping(mapping.get("input_contract"), "obligation_spec.input_contract")
            ),
            produces=_load_tuple(mapping.get("produces", []), ProducedArtifactSpec.from_dict, "obligation_spec.produces"),
            execution_policy_ref=_optional_string(mapping.get("execution_policy_ref")),
        )


@dataclass(frozen=True, slots=True)
class ProtocolSpec:
    artifact_type: str
    slots: tuple[str, ...]
    invariants: tuple[str, ...] = ()
    required_claim_scopes: tuple[str, ...] = ()
    obligations: tuple[ObligationSpec, ...] = ()

    schema_version: str = field(init=False, default=DSL_SCHEMA_VERSION)
    kind: str = field(init=False, default=PROTOCOL_SPEC_KIND)

    def __post_init__(self) -> None:
        object.__setattr__(self, "artifact_type", _require_string(self.artifact_type, "artifact_type"))
        object.__setattr__(self, "slots", _normalize_string_tuple(self.slots, "slots"))
        object.__setattr__(self, "invariants", _normalize_string_tuple(self.invariants, "invariants"))
        object.__setattr__(
            self,
            "required_claim_scopes",
            _normalize_string_tuple(self.required_claim_scopes, "required_claim_scopes"),
        )
        object.__setattr__(self, "obligations", _coerce_tuple(self.obligations, ObligationSpec, "obligations"))

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "kind": self.kind,
            "artifact_type": self.artifact_type,
            "slots": list(self.slots),
            "invariants": list(self.invariants),
            "required_claim_scopes": list(self.required_claim_scopes),
            "obligations": [obligation.to_dict() for obligation in self.obligations],
        }

    @classmethod
    def from_dict(cls, raw: Mapping[str, object]) -> ProtocolSpec:
        mapping = _validate_record(raw, _PROTOCOL_SPEC_FIELDS, PROTOCOL_SPEC_KIND, "protocol_spec")
        return cls(
            artifact_type=_require_string(mapping.get("artifact_type"), "protocol_spec.artifact_type"),
            slots=_load_string_tuple(mapping.get("slots", []), "protocol_spec.slots"),
            invariants=_load_string_tuple(mapping.get("invariants", []), "protocol_spec.invariants"),
            required_claim_scopes=_load_string_tuple(
                mapping.get("required_claim_scopes", []),
                "protocol_spec.required_claim_scopes",
            ),
            obligations=_load_tuple(mapping.get("obligations", []), ObligationSpec.from_dict, "protocol_spec.obligations"),
        )


@dataclass(frozen=True, slots=True)
class ExecutionPolicy:
    id: str
    runner: str
    role: str | None = None
    provider: str | None = None
    model: str | None = None
    tool: str | None = None
    timeout_seconds: int | None = None
    retry: int = 0
    budget: Mapping[str, object] = field(default_factory=dict)

    schema_version: str = field(init=False, default=DSL_SCHEMA_VERSION)
    kind: str = field(init=False, default=EXECUTION_POLICY_KIND)

    def __post_init__(self) -> None:
        object.__setattr__(self, "id", _require_string(self.id, "id"))
        object.__setattr__(self, "runner", _require_string(self.runner, "runner"))
        object.__setattr__(self, "role", _optional_string(self.role))
        object.__setattr__(self, "provider", _optional_string(self.provider))
        object.__setattr__(self, "model", _optional_string(self.model))
        object.__setattr__(self, "tool", _optional_string(self.tool))
        if self.timeout_seconds is not None and self.timeout_seconds < 1:
            raise ValueError("timeout_seconds must be positive")
        if self.retry < 0:
            raise ValueError("retry must be non-negative")
        object.__setattr__(self, "budget", _normalize_json_mapping(self.budget, "budget"))

    def to_dict(self) -> dict[str, object]:
        data: dict[str, object] = {
            "schema_version": self.schema_version,
            "kind": self.kind,
            "id": self.id,
            "runner": self.runner,
            "retry": self.retry,
            "budget": dict(self.budget),
        }
        for key in ("role", "provider", "model", "tool", "timeout_seconds"):
            value = getattr(self, key)
            if value is not None:
                data[key] = value
        return data

    @classmethod
    def from_dict(cls, raw: Mapping[str, object]) -> ExecutionPolicy:
        mapping = _validate_record(raw, _EXECUTION_POLICY_FIELDS, EXECUTION_POLICY_KIND, "execution_policy")
        return cls(
            id=_require_string(mapping.get("id"), "execution_policy.id"),
            runner=_require_string(mapping.get("runner"), "execution_policy.runner"),
            role=_optional_string(mapping.get("role")),
            provider=_optional_string(mapping.get("provider")),
            model=_optional_string(mapping.get("model")),
            tool=_optional_string(mapping.get("tool")),
            timeout_seconds=_optional_int(mapping.get("timeout_seconds"), "execution_policy.timeout_seconds"),
            retry=_optional_int(mapping.get("retry"), "execution_policy.retry") or 0,
            budget=_normalize_json_mapping(mapping.get("budget", {}), "execution_policy.budget"),
        )


@dataclass(frozen=True, slots=True)
class ObligationIntent:
    intent_kind: str
    target_artifact: str
    missing_scopes: tuple[str, ...] = ()
    reasons: tuple[str, ...] = ()
    data: Mapping[str, object] = field(default_factory=dict)

    schema_version: str = field(init=False, default=DSL_SCHEMA_VERSION)
    kind: str = field(init=False, default=OBLIGATION_INTENT_KIND)

    def __post_init__(self) -> None:
        object.__setattr__(self, "intent_kind", _require_string(self.intent_kind, "intent_kind"))
        object.__setattr__(self, "target_artifact", _require_ref(self.target_artifact, "target_artifact"))
        object.__setattr__(self, "missing_scopes", _normalize_string_tuple(self.missing_scopes, "missing_scopes"))
        object.__setattr__(self, "reasons", _normalize_string_tuple(self.reasons, "reasons"))
        object.__setattr__(self, "data", _normalize_json_mapping(self.data, "data"))

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "kind": self.kind,
            "intent_kind": self.intent_kind,
            "target_artifact": self.target_artifact,
            "missing_scopes": list(self.missing_scopes),
            "reasons": list(self.reasons),
            "data": dict(self.data),
        }

    @classmethod
    def from_dict(cls, raw: Mapping[str, object]) -> ObligationIntent:
        mapping = _validate_record(raw, _OBLIGATION_INTENT_FIELDS, OBLIGATION_INTENT_KIND, "obligation_intent")
        return cls(
            intent_kind=_require_string(mapping.get("intent_kind"), "obligation_intent.intent_kind"),
            target_artifact=_require_string(mapping.get("target_artifact"), "obligation_intent.target_artifact"),
            missing_scopes=_load_string_tuple(mapping.get("missing_scopes", []), "obligation_intent.missing_scopes"),
            reasons=_load_string_tuple(mapping.get("reasons", []), "obligation_intent.reasons"),
            data=_normalize_json_mapping(mapping.get("data", {}), "obligation_intent.data"),
        )


@dataclass(frozen=True, slots=True)
class MaterializedInputSet:
    refs: tuple[str, ...]
    fingerprint: str

    schema_version: str = field(init=False, default=DSL_SCHEMA_VERSION)
    kind: str = field(init=False, default=MATERIALIZED_INPUT_SET_KIND)

    def __post_init__(self) -> None:
        object.__setattr__(self, "refs", _normalize_ref_tuple(self.refs, "refs"))
        object.__setattr__(self, "fingerprint", _require_fingerprint(self.fingerprint, "fingerprint"))

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "kind": self.kind,
            "refs": list(self.refs),
            "fingerprint": self.fingerprint,
        }

    @classmethod
    def from_dict(cls, raw: Mapping[str, object]) -> MaterializedInputSet:
        mapping = _validate_record(
            raw,
            _MATERIALIZED_INPUT_SET_FIELDS,
            MATERIALIZED_INPUT_SET_KIND,
            "materialized_input_set",
        )
        return cls(
            refs=_load_ref_tuple(mapping.get("refs", []), "materialized_input_set.refs"),
            fingerprint=_require_string(mapping.get("fingerprint"), "materialized_input_set.fingerprint"),
        )


@dataclass(frozen=True, slots=True)
class CompiledObligation:
    id: str
    spec_ref: str
    target_artifact: str
    bound_inputs: tuple[str, ...]
    materialized_input_set: MaterializedInputSet
    execution_policy_ref: str | None = None
    status: str = "pending"

    schema_version: str = field(init=False, default=DSL_SCHEMA_VERSION)
    kind: str = field(init=False, default=COMPILED_OBLIGATION_KIND)

    def __post_init__(self) -> None:
        object.__setattr__(self, "id", _require_string(self.id, "id"))
        object.__setattr__(self, "spec_ref", _require_string(self.spec_ref, "spec_ref"))
        object.__setattr__(self, "target_artifact", _require_ref(self.target_artifact, "target_artifact"))
        object.__setattr__(self, "bound_inputs", _normalize_ref_tuple(self.bound_inputs, "bound_inputs"))
        if not isinstance(self.materialized_input_set, MaterializedInputSet):
            raise TypeError("materialized_input_set must be MaterializedInputSet")
        if set(self.bound_inputs) != set(self.materialized_input_set.refs):
            raise ValueError("bound_inputs must match materialized_input_set.refs")
        object.__setattr__(self, "execution_policy_ref", _optional_string(self.execution_policy_ref))
        object.__setattr__(self, "status", _require_string(self.status, "status"))

    def to_dict(self) -> dict[str, object]:
        data: dict[str, object] = {
            "schema_version": self.schema_version,
            "kind": self.kind,
            "id": self.id,
            "spec_ref": self.spec_ref,
            "target_artifact": self.target_artifact,
            "bound_inputs": list(self.bound_inputs),
            "materialized_input_set": self.materialized_input_set.to_dict(),
            "status": self.status,
        }
        if self.execution_policy_ref is not None:
            data["execution_policy_ref"] = self.execution_policy_ref
        return data

    @classmethod
    def from_dict(cls, raw: Mapping[str, object]) -> CompiledObligation:
        mapping = _validate_record(
            raw,
            _COMPILED_OBLIGATION_FIELDS,
            COMPILED_OBLIGATION_KIND,
            "compiled_obligation",
        )
        return cls(
            id=_require_string(mapping.get("id"), "compiled_obligation.id"),
            spec_ref=_require_string(mapping.get("spec_ref"), "compiled_obligation.spec_ref"),
            target_artifact=_require_string(mapping.get("target_artifact"), "compiled_obligation.target_artifact"),
            bound_inputs=_load_ref_tuple(mapping.get("bound_inputs", []), "compiled_obligation.bound_inputs"),
            materialized_input_set=MaterializedInputSet.from_dict(
                _require_mapping(mapping.get("materialized_input_set"), "compiled_obligation.materialized_input_set")
            ),
            execution_policy_ref=_optional_string(mapping.get("execution_policy_ref")),
            status=_optional_string(mapping.get("status")) or "pending",
        )


_INPUT_MODES = frozenset({INPUT_MODE_REQUIRED, INPUT_MODE_OPTIONAL, INPUT_MODE_FORBIDDEN})


def _validate_record(
    raw: Mapping[str, object],
    allowed_fields: frozenset[str],
    expected_kind: str,
    field_name: str,
) -> Mapping[str, object]:
    mapping = _require_mapping(raw, field_name)
    _raise_unknown_fields(mapping, allowed_fields, field_name)
    schema_version = _optional_string(mapping.get("schema_version"))
    if schema_version not in (None, DSL_SCHEMA_VERSION):
        raise ValueError(f"{field_name}.schema_version must be {DSL_SCHEMA_VERSION!r}, got {schema_version!r}")
    kind = _optional_string(mapping.get("kind")) or expected_kind
    if kind != expected_kind:
        raise ValueError(f"{field_name}.kind must be {expected_kind!r}, got {kind!r}")
    return mapping


def _raise_unknown_fields(mapping: Mapping[str, object], allowed_fields: frozenset[str], field_name: str) -> None:
    unknown = find_unknown_fields(mapping, allowed_fields)
    if unknown:
        joined = ", ".join(unknown)
        raise ValueError(f"{field_name} contains unknown fields: {joined}")


def _load_selectors(value: object, mode: str, field_name: str) -> tuple[RefSelector, ...]:
    items = _require_list(value, field_name)
    return tuple(
        _selector_with_mode(RefSelector.from_dict(_require_mapping(item, f"{field_name}[{index}]")), mode)
        for index, item in enumerate(items)
    )


def _coerce_selectors(values: Sequence[RefSelector], mode: str, field_name: str) -> tuple[RefSelector, ...]:
    normalized = _coerce_tuple(values, RefSelector, field_name)
    return tuple(_selector_with_mode(selector, mode) for selector in normalized)


def _selector_with_mode(selector: RefSelector, mode: str) -> RefSelector:
    if selector.mode != mode:
        return RefSelector(ref=selector.ref, mode=mode, reason=selector.reason)
    return selector


def _load_tuple(value: object, loader, field_name: str) -> tuple[object, ...]:
    items = _require_list(value, field_name)
    return tuple(loader(_require_mapping(item, f"{field_name}[{index}]")) for index, item in enumerate(items))


def _coerce_tuple(values: Sequence[object], expected_type: type, field_name: str) -> tuple[object, ...]:
    if isinstance(values, (str, bytes, bytearray)) or not isinstance(values, Sequence):
        raise TypeError(f"{field_name} must be a sequence of {expected_type.__name__}")
    normalized: list[object] = []
    for index, item in enumerate(values):
        if not isinstance(item, expected_type):
            raise TypeError(f"{field_name}[{index}] must be {expected_type.__name__}, got {type(item).__name__}")
        normalized.append(item)
    return tuple(normalized)


def _load_string_tuple(value: object, field_name: str) -> tuple[str, ...]:
    return _normalize_string_tuple(_require_list(value, field_name), field_name)


def _load_ref_tuple(value: object, field_name: str) -> tuple[str, ...]:
    return _normalize_ref_tuple(_require_list(value, field_name), field_name)


def _normalize_string_tuple(values: Sequence[object], field_name: str) -> tuple[str, ...]:
    if isinstance(values, (str, bytes, bytearray)) or not isinstance(values, Sequence):
        raise TypeError(f"{field_name} must be a sequence of str")
    normalized: list[str] = []
    for index, value in enumerate(values):
        normalized.append(_require_string(value, f"{field_name}[{index}]"))
    return tuple(normalized)


def _normalize_ref_tuple(values: Sequence[object], field_name: str) -> tuple[str, ...]:
    if isinstance(values, (str, bytes, bytearray)) or not isinstance(values, Sequence):
        raise TypeError(f"{field_name} must be a sequence of refs")
    normalized: list[str] = []
    for index, value in enumerate(values):
        normalized.append(_require_ref(value, f"{field_name}[{index}]"))
    return tuple(normalized)


def _normalize_json_mapping(value: object, field_name: str) -> dict[str, object]:
    mapping = _require_mapping(value, field_name)
    return {
        str(key): _normalize_json_value(item, f"{field_name}.{key}")
        for key, item in sorted(mapping.items(), key=lambda pair: str(pair[0]))
    }


def _normalize_json_value(value: object, field_name: str) -> object:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Mapping):
        return _normalize_json_mapping(value, field_name)
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [_normalize_json_value(item, f"{field_name}[{index}]") for index, item in enumerate(value)]
    raise TypeError(f"{field_name} must be JSON-serializable")


def _require_mapping(value: object, field_name: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise TypeError(f"{field_name} must be a mapping, got {type(value).__name__}")
    return value


def _require_list(value: object, field_name: str) -> list[object]:
    if not isinstance(value, list):
        raise TypeError(f"{field_name} must be a list, got {type(value).__name__}")
    return value


def _require_string(value: object, field_name: str) -> str:
    normalized = _optional_string(value)
    if normalized is None:
        raise ValueError(f"{field_name} is required")
    return normalized


def _require_ref(value: object, field_name: str) -> str:
    normalized = _require_string(value, field_name)
    if "://" not in normalized:
        raise ValueError(f"{field_name} must be a URI-like ref")
    return normalized


def _require_fingerprint(value: object, field_name: str) -> str:
    normalized = _require_string(value, field_name)
    if not normalized.startswith("sha256:"):
        raise ValueError(f"{field_name} must start with 'sha256:'")
    return normalized


def _require_one_of(value: object, field_name: str, allowed_values: frozenset[str]) -> str:
    normalized = _require_string(value, field_name)
    if normalized not in allowed_values:
        joined = ", ".join(sorted(allowed_values))
        raise ValueError(f"{field_name} must be one of: {joined}; got {normalized!r}")
    return normalized


def _optional_string(value: object) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip()
    return normalized or None


def _optional_int(value: object, field_name: str) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{field_name} must be int")
    return value


__all__ = [
    "COMPILED_OBLIGATION_KIND",
    "DSL_SCHEMA_VERSION",
    "EXECUTION_POLICY_KIND",
    "INPUT_CONTRACT_KIND",
    "INPUT_MODE_FORBIDDEN",
    "INPUT_MODE_OPTIONAL",
    "INPUT_MODE_REQUIRED",
    "MATERIALIZED_INPUT_SET_KIND",
    "OBLIGATION_INTENT_KIND",
    "OBLIGATION_SPEC_KIND",
    "PROTOCOL_SPEC_KIND",
    "CompiledObligation",
    "ExecutionPolicy",
    "InputContract",
    "MaterializedInputSet",
    "ObligationIntent",
    "ObligationSpec",
    "ProducedArtifactSpec",
    "ProtocolSpec",
    "RefSelector",
]
