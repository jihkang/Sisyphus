from __future__ import annotations

from collections.abc import Mapping

from ..application.artifacts.execution_policy import (
    DEFAULT_EXECUTION_POLICY_REGISTRY_DECLARATION,
    EXECUTION_POLICY_REGISTRY_SCHEMA_VERSION,
    EXECUTION_POLICY_WITNESS_DEFAULT,
    EXECUTION_RUNNER_SISYPHUS_VERIFY,
    execution_policy_receipt_fields,
    resolve_execution_policy as resolve_policy,
    supported_execution_runners,
)
from ..application.codecs.execution_policies import (
    decode_execution_policy_registry,
    encode_execution_policy_registry,
)
from ..domain.artifact.dsl import ExecutionPolicy
from ..infra.artifacts.declarations import load_execution_policy_declaration


def default_execution_policy_registry() -> dict[str, ExecutionPolicy]:
    return load_execution_policy_registry_declaration()


def load_execution_policy_registry_declaration(
    relative_path: str = DEFAULT_EXECUTION_POLICY_REGISTRY_DECLARATION,
) -> dict[str, ExecutionPolicy]:
    return load_execution_policy_declaration(relative_path)


def resolve_execution_policy(
    policy_ref: str | None,
    *,
    registry: Mapping[str, ExecutionPolicy] | None = None,
) -> ExecutionPolicy | None:
    return resolve_policy(
        policy_ref,
        registry=registry or default_execution_policy_registry(),
    )


def execution_policy_registry_to_dict(
    registry: Mapping[str, ExecutionPolicy] | None = None,
) -> dict[str, object]:
    return encode_execution_policy_registry(
        registry or default_execution_policy_registry()
    )


def execution_policy_registry_from_dict(
    raw: Mapping[str, object],
) -> dict[str, ExecutionPolicy]:
    return decode_execution_policy_registry(raw)


__all__ = [
    "DEFAULT_EXECUTION_POLICY_REGISTRY_DECLARATION",
    "EXECUTION_POLICY_REGISTRY_SCHEMA_VERSION",
    "EXECUTION_POLICY_WITNESS_DEFAULT",
    "EXECUTION_RUNNER_SISYPHUS_VERIFY",
    "default_execution_policy_registry",
    "execution_policy_receipt_fields",
    "execution_policy_registry_from_dict",
    "execution_policy_registry_to_dict",
    "load_execution_policy_registry_declaration",
    "resolve_execution_policy",
    "supported_execution_runners",
]
