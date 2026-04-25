from __future__ import annotations

from collections.abc import Mapping

from .dsl import ExecutionPolicy


EXECUTION_POLICY_REGISTRY_SCHEMA_VERSION = "sisyphus.execution_policy_registry.v1"

EXECUTION_POLICY_WITNESS_DEFAULT = "witness_default"
EXECUTION_RUNNER_SISYPHUS_VERIFY = "sisyphus.verify"


def default_execution_policy_registry() -> dict[str, ExecutionPolicy]:
    policy = ExecutionPolicy(
        id=EXECUTION_POLICY_WITNESS_DEFAULT,
        runner=EXECUTION_RUNNER_SISYPHUS_VERIFY,
        role="witness",
        provider="local",
        tool=EXECUTION_RUNNER_SISYPHUS_VERIFY,
        timeout_seconds=600,
        retry=0,
    )
    return {policy.id: policy}


def resolve_execution_policy(
    policy_ref: str | None,
    *,
    registry: Mapping[str, ExecutionPolicy] | None = None,
) -> ExecutionPolicy | None:
    if policy_ref is None:
        return None
    return (registry or default_execution_policy_registry()).get(policy_ref)


def execution_policy_registry_to_dict(
    registry: Mapping[str, ExecutionPolicy] | None = None,
) -> dict[str, object]:
    resolved = registry or default_execution_policy_registry()
    return {
        "schema_version": EXECUTION_POLICY_REGISTRY_SCHEMA_VERSION,
        "policies": {policy_id: policy.to_dict() for policy_id, policy in sorted(resolved.items())},
    }


def execution_policy_registry_from_dict(raw: Mapping[str, object]) -> dict[str, ExecutionPolicy]:
    raw_policies = raw.get("policies", {})
    if not isinstance(raw_policies, Mapping):
        raise TypeError("execution policy registry policies must be a mapping")
    policies: dict[str, ExecutionPolicy] = {}
    for policy_id, policy_raw in raw_policies.items():
        if not isinstance(policy_raw, Mapping):
            raise TypeError(f"execution policy {policy_id!s} must be a mapping")
        policy = ExecutionPolicy.from_dict(policy_raw)
        if str(policy_id) != policy.id:
            raise ValueError(f"execution policy key {policy_id!r} does not match policy id {policy.id!r}")
        policies[policy.id] = policy
    return policies


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
    "EXECUTION_POLICY_REGISTRY_SCHEMA_VERSION",
    "EXECUTION_POLICY_WITNESS_DEFAULT",
    "EXECUTION_RUNNER_SISYPHUS_VERIFY",
    "default_execution_policy_registry",
    "execution_policy_receipt_fields",
    "execution_policy_registry_from_dict",
    "execution_policy_registry_to_dict",
    "resolve_execution_policy",
    "supported_execution_runners",
]
