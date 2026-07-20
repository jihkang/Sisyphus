from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field



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


@dataclass(frozen=True, slots=True)
class RefSelector:
    ref: str
    mode: str = INPUT_MODE_REQUIRED
    reason: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "ref", _require_ref(self.ref, "ref"))
        object.__setattr__(self, "mode", _require_one_of(self.mode, "mode", _INPUT_MODES))
        object.__setattr__(self, "reason", _optional_string(self.reason))

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

@dataclass(frozen=True, slots=True)
class ProducedArtifactSpec:
    artifact_type: str
    claim: str | None = None
    scope: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "artifact_type", _require_string(self.artifact_type, "artifact_type"))
        object.__setattr__(self, "claim", _optional_string(self.claim))
        object.__setattr__(self, "scope", _optional_string(self.scope))

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

@dataclass(frozen=True, slots=True)
class MaterializedInputSet:
    refs: tuple[str, ...]
    fingerprint: str

    schema_version: str = field(init=False, default=DSL_SCHEMA_VERSION)
    kind: str = field(init=False, default=MATERIALIZED_INPUT_SET_KIND)

    def __post_init__(self) -> None:
        object.__setattr__(self, "refs", _normalize_ref_tuple(self.refs, "refs"))
        object.__setattr__(self, "fingerprint", _require_fingerprint(self.fingerprint, "fingerprint"))

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

_INPUT_MODES = frozenset({INPUT_MODE_REQUIRED, INPUT_MODE_OPTIONAL, INPUT_MODE_FORBIDDEN})


def _coerce_selectors(values: Sequence[RefSelector], mode: str, field_name: str) -> tuple[RefSelector, ...]:
    normalized = _coerce_tuple(values, RefSelector, field_name)
    return tuple(_selector_with_mode(selector, mode) for selector in normalized)


def _selector_with_mode(selector: RefSelector, mode: str) -> RefSelector:
    if selector.mode != mode:
        return RefSelector(ref=selector.ref, mode=mode, reason=selector.reason)
    return selector


def _coerce_tuple(values: Sequence[object], expected_type: type, field_name: str) -> tuple[object, ...]:
    if isinstance(values, (str, bytes, bytearray)) or not isinstance(values, Sequence):
        raise TypeError(f"{field_name} must be a sequence of {expected_type.__name__}")
    normalized: list[object] = []
    for index, item in enumerate(values):
        if not isinstance(item, expected_type):
            raise TypeError(f"{field_name}[{index}] must be {expected_type.__name__}, got {type(item).__name__}")
        normalized.append(item)
    return tuple(normalized)


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
