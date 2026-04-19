from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, TypeAlias


EVOLUTION_REVIEW_GATE_PLAN_REVIEW = "plan_review"
EVOLUTION_REVIEW_GATE_OPERATOR_APPROVAL = "operator_approval"
EVOLUTION_REVIEW_GATE_SPEC_FREEZE = "spec_freeze"
EVOLUTION_REVIEW_GATE_PROVIDER_EXECUTION = "provider_execution"
EVOLUTION_REVIEW_GATE_VERIFY = "verify"
EVOLUTION_REVIEW_GATE_RECEIPT = "receipt"

EVOLUTION_DEFAULT_REVIEW_GATES = (
    EVOLUTION_REVIEW_GATE_PLAN_REVIEW,
    EVOLUTION_REVIEW_GATE_OPERATOR_APPROVAL,
    EVOLUTION_REVIEW_GATE_SPEC_FREEZE,
    EVOLUTION_REVIEW_GATE_PROVIDER_EXECUTION,
    EVOLUTION_REVIEW_GATE_VERIFY,
    EVOLUTION_REVIEW_GATE_RECEIPT,
)

EVOLUTION_PROMOTION_INTENT_OBSERVE_ONLY = "observe_only"
EVOLUTION_PROMOTION_INTENT_CANDIDATE_ONLY = "candidate_only"
EVOLUTION_PROMOTION_INTENT_REQUEST_FOLLOWUP = "request_followup"

EvolutionReviewGate: TypeAlias = Literal[
    "plan_review",
    "operator_approval",
    "spec_freeze",
    "provider_execution",
    "verify",
    "receipt",
]

EvolutionPromotionIntent: TypeAlias = Literal[
    "observe_only",
    "candidate_only",
    "request_followup",
]


@dataclass(frozen=True, slots=True)
class EvolutionVerificationObligation:
    claim: str
    method: str
    required: bool = True


@dataclass(frozen=True, slots=True)
class EvolutionEvidenceSummary:
    kind: str
    summary: str
    locator: str | None = None


@dataclass(frozen=True, slots=True)
class EvolutionFollowupRequest:
    source_run_id: str
    candidate_id: str
    title: str
    summary: str
    requested_task_type: str
    target_scope: tuple[str, ...]
    instruction_set: tuple[str, ...]
    owned_paths: tuple[str, ...]
    expected_verification_obligations: tuple[EvolutionVerificationObligation, ...]
    evidence_summary: tuple[EvolutionEvidenceSummary, ...]
    promotion_intent: EvolutionPromotionIntent
    required_review_gates: tuple[EvolutionReviewGate, ...] = EVOLUTION_DEFAULT_REVIEW_GATES
    request_only: bool = True
    permits_plan_approval: bool = False
    permits_spec_freeze: bool = False
    permits_execution: bool = False
    permits_promotion: bool = False
