from __future__ import annotations

from pathlib import Path
import sys
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from sisyphus.execution_policy import (
    EXECUTION_POLICY_REGISTRY_SCHEMA_VERSION,
    EXECUTION_POLICY_WITNESS_DEFAULT,
    EXECUTION_RUNNER_SISYPHUS_VERIFY,
    default_execution_policy_registry,
    execution_policy_receipt_fields,
    execution_policy_registry_from_dict,
    execution_policy_registry_to_dict,
    resolve_execution_policy,
)


class ExecutionPolicyRegistryTests(unittest.TestCase):
    def test_default_registry_exposes_replaceable_witness_overlay(self) -> None:
        registry = default_execution_policy_registry()
        policy = resolve_execution_policy(EXECUTION_POLICY_WITNESS_DEFAULT, registry=registry)

        self.assertIsNotNone(policy)
        assert policy is not None
        self.assertEqual(policy.runner, EXECUTION_RUNNER_SISYPHUS_VERIFY)
        self.assertEqual(policy.role, "witness")
        self.assertEqual(policy.provider, "local")

    def test_registry_round_trips_by_policy_id(self) -> None:
        registry = default_execution_policy_registry()
        rendered = execution_policy_registry_to_dict(registry)
        restored = execution_policy_registry_from_dict(rendered)

        self.assertEqual(rendered["schema_version"], EXECUTION_POLICY_REGISTRY_SCHEMA_VERSION)
        self.assertEqual(restored, registry)

    def test_receipt_fields_preserve_resolved_execution_boundary(self) -> None:
        policy = default_execution_policy_registry()[EXECUTION_POLICY_WITNESS_DEFAULT]

        receipt = execution_policy_receipt_fields(policy)

        self.assertEqual(receipt["execution_policy_ref"], EXECUTION_POLICY_WITNESS_DEFAULT)
        self.assertEqual(receipt["runner"], EXECUTION_RUNNER_SISYPHUS_VERIFY)
        self.assertEqual(receipt["role"], "witness")
        self.assertEqual(receipt["provider"], "local")

    def test_policy_key_mismatch_is_rejected(self) -> None:
        rendered = execution_policy_registry_to_dict()
        rendered["policies"] = {"different": rendered["policies"][EXECUTION_POLICY_WITNESS_DEFAULT]}

        with self.assertRaisesRegex(ValueError, "does not match"):
            execution_policy_registry_from_dict(rendered)


if __name__ == "__main__":
    unittest.main()
