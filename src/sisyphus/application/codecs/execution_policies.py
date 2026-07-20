from __future__ import annotations

from collections.abc import Mapping

from ..artifacts.execution_policy import EXECUTION_POLICY_REGISTRY_SCHEMA_VERSION
from ...domain.artifact.dsl import ExecutionPolicy
from .artifact_dsl import decode_execution_policy, encode_execution_policy


def encode_execution_policy_registry(
    registry: Mapping[str, ExecutionPolicy],
) -> dict[str, object]:
    return {
        "schema_version": EXECUTION_POLICY_REGISTRY_SCHEMA_VERSION,
        "policies": {
            policy_id: encode_execution_policy(policy)
            for policy_id, policy in sorted(registry.items())
        },
    }


def decode_execution_policy_registry(
    raw: Mapping[str, object],
) -> dict[str, ExecutionPolicy]:
    raw_policies = raw.get("policies", {})
    if not isinstance(raw_policies, Mapping):
        raise TypeError("execution policy registry policies must be a mapping")
    policies: dict[str, ExecutionPolicy] = {}
    for policy_id, policy_raw in raw_policies.items():
        if not isinstance(policy_raw, Mapping):
            raise TypeError(f"execution policy {policy_id!s} must be a mapping")
        policy = decode_execution_policy(policy_raw)
        if str(policy_id) != policy.id:
            raise ValueError(
                f"execution policy key {policy_id!r} does not match policy id {policy.id!r}"
            )
        policies[policy.id] = policy
    return policies


__all__ = ["decode_execution_policy_registry", "encode_execution_policy_registry"]
