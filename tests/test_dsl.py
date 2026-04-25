from __future__ import annotations

from pathlib import Path
import sys
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from sisyphus.dsl import (
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


class DslModelTests(unittest.TestCase):
    def test_protocol_spec_preserves_slot_selectors_separate_from_runtime_artifact_refs(self) -> None:
        input_contract = InputContract(
            required=(
                RefSelector("slot://spec#acceptance_criteria"),
                RefSelector("slot://selected_implementation"),
                RefSelector("slot://test_obligations"),
            ),
            optional=(RefSelector("slot://execution_receipts/*"),),
            forbidden=(RefSelector("external://unrelated_prior_outputs/*"),),
            closure={
                "dependency_rule": "current_bound_slots_only",
                "stale_on": [
                    "spec_revision_changed",
                    "selected_implementation_changed",
                    "test_obligation_changed",
                ],
            },
        )
        obligation = ObligationSpec(
            id="verify_composite_feature",
            obligation_kind="verification",
            input_contract=input_contract,
            produces=(
                ProducedArtifactSpec(
                    artifact_type="verification_claim",
                    claim="acceptance_criteria_satisfied",
                    scope="composite",
                ),
            ),
            execution_policy_ref="witness_default",
        )
        protocol = ProtocolSpec(
            artifact_type="feature_change",
            slots=(
                "spec",
                "implementation_candidates",
                "selected_implementation",
                "test_obligations",
                "verification_claims",
            ),
            invariants=(
                "selected_implementation_is_candidate",
                "claims_bind_current_inputs",
            ),
            required_claim_scopes=("local", "cross", "composite"),
            obligations=(obligation,),
        )

        restored = ProtocolSpec.from_dict(protocol.to_dict())

        self.assertEqual(restored, protocol)
        self.assertEqual(
            restored.obligations[0].input_contract.required[0].ref,
            "slot://spec#acceptance_criteria",
        )
        self.assertEqual(restored.obligations[0].produces[0].scope, "composite")

    def test_obligation_intent_and_compiled_obligation_are_distinct_runtime_shapes(self) -> None:
        intent = ObligationIntent(
            intent_kind="verify_required_claims",
            target_artifact="artifact://feature_change_123",
            missing_scopes=("composite",),
            reasons=("verification_scope:composite",),
        )
        materialized_inputs = MaterializedInputSet(
            refs=(
                "artifact://feature_spec_v17#acceptance_criteria",
                "artifact://impl_candidate_v42",
                "artifact://test_bundle_v9",
            ),
            fingerprint="sha256:abc123",
        )
        compiled = CompiledObligation(
            id="obligation-verify-composite-feature-123",
            spec_ref="verify_composite_feature",
            target_artifact=intent.target_artifact,
            bound_inputs=materialized_inputs.refs,
            materialized_input_set=materialized_inputs,
            execution_policy_ref="witness_default",
        )

        restored_intent = ObligationIntent.from_dict(intent.to_dict())
        restored_compiled = CompiledObligation.from_dict(compiled.to_dict())

        self.assertEqual(restored_intent.intent_kind, "verify_required_claims")
        self.assertEqual(restored_compiled.spec_ref, "verify_composite_feature")
        self.assertEqual(
            restored_compiled.materialized_input_set.fingerprint,
            "sha256:abc123",
        )

    def test_execution_policy_round_trips_as_replaceable_overlay(self) -> None:
        policy = ExecutionPolicy(
            id="witness_default",
            runner="agent",
            role="witness",
            provider="codex",
            timeout_seconds=600,
            retry=1,
            budget={"max_tokens": 12000},
        )

        restored = ExecutionPolicy.from_dict(policy.to_dict())

        self.assertEqual(restored, policy)
        self.assertEqual(restored.provider, "codex")

    def test_invalid_refs_and_mismatched_materialized_inputs_are_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "URI-like ref"):
            RefSelector("spec#acceptance_criteria")

        with self.assertRaisesRegex(ValueError, "sha256"):
            MaterializedInputSet(refs=("artifact://spec",), fingerprint="abc123")

        with self.assertRaisesRegex(ValueError, "bound_inputs must match"):
            CompiledObligation(
                id="obligation-bad",
                spec_ref="verify_composite_feature",
                target_artifact="artifact://feature_change_123",
                bound_inputs=("artifact://spec",),
                materialized_input_set=MaterializedInputSet(
                    refs=("artifact://different",),
                    fingerprint="sha256:abc123",
                ),
            )


if __name__ == "__main__":
    unittest.main()
