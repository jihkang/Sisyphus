from __future__ import annotations

from collections.abc import Mapping

from ...domain.artifact.dsl import ExecutionPolicy


EXECUTION_POLICY_REGISTRY_SCHEMA_VERSION = "sisyphus.execution_policy_registry.v1"

EXECUTION_POLICY_WITNESS_DEFAULT = "witness_default"
EXECUTION_RUNNER_SISYPHUS_VERIFY = "sisyphus.verify"
DEFAULT_EXECUTION_POLICY_REGISTRY_DECLARATION = "declarations/execution_policies.json"


def resolve_execution_policy(
    policy_ref: str | None,
    *,
    registry: Mapping[str, ExecutionPolicy],
) -> ExecutionPolicy | None:
    if policy_ref is None:
        return None
    return registry.get(policy_ref)


def execution_policy_receipt_fields(policy: ExecutionPolicy) -> dict[str, object]:
    fields: dict[str, object] = {
        "execution_policy_ref": policy.id,
        "runner": policy.runner,
    }
    for key in ("role", "provider", "model", "tool", "timeout_seconds", "retry"):
        value = getattr(policy, key)
        if value is not None:
            fields[key] = value
    return fields


def supported_execution_runners() -> tuple[str, ...]:
    return (EXECUTION_RUNNER_SISYPHUS_VERIFY,)


__all__ = [
    "DEFAULT_EXECUTION_POLICY_REGISTRY_DECLARATION",
    "EXECUTION_POLICY_REGISTRY_SCHEMA_VERSION",
    "EXECUTION_POLICY_WITNESS_DEFAULT",
    "EXECUTION_RUNNER_SISYPHUS_VERIFY",
    "execution_policy_receipt_fields",
    "resolve_execution_policy",
    "supported_execution_runners",
]
