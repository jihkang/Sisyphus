"""Compatibility facade for execution-policy composition."""

from .composition.execution_policy import (
    DEFAULT_EXECUTION_POLICY_REGISTRY_DECLARATION,
    EXECUTION_POLICY_REGISTRY_SCHEMA_VERSION,
    EXECUTION_POLICY_WITNESS_DEFAULT,
    EXECUTION_RUNNER_SISYPHUS_VERIFY,
    default_execution_policy_registry,
    execution_policy_receipt_fields,
    execution_policy_registry_from_dict,
    execution_policy_registry_to_dict,
    load_execution_policy_registry_declaration,
    resolve_execution_policy,
    supported_execution_runners,
)


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
