from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import ClassVar, Literal, TypeAlias


EVOLUTION_ARTIFACT_OWNER_EVOLUTION = "evolution"
EVOLUTION_ARTIFACT_OWNER_SISYPHUS = "sisyphus"

EVOLUTION_ARTIFACT_STATUS_PLANNED = "planned"
EVOLUTION_ARTIFACT_STATUS_AVAILABLE = "available"
EVOLUTION_ARTIFACT_STATUS_RECORDED = "recorded"
EVOLUTION_ARTIFACT_STATUS_FUTURE = "future"

EVOLUTION_ARTIFACT_KIND_RUN_SPEC = "evolution_run_spec"
EVOLUTION_ARTIFACT_KIND_DATASET = "evolution_dataset"
EVOLUTION_ARTIFACT_KIND_CANDIDATE = "evolution_candidate"
EVOLUTION_ARTIFACT_KIND_EVALUATION = "evolution_evaluation"
EVOLUTION_ARTIFACT_KIND_REPORT = "evolution_report"
EVOLUTION_ARTIFACT_KIND_FOLLOWUP_REQUEST = "evolution_followup_request"
EVOLUTION_ARTIFACT_KIND_EXECUTION_RECEIPT = "execution_receipt"
EVOLUTION_ARTIFACT_KIND_VERIFICATION = "verification"
EVOLUTION_ARTIFACT_KIND_PROMOTION_DECISION = "promotion_decision"

EvolutionArtifactOwner: TypeAlias = Literal["evolution", "sisyphus"]
EvolutionArtifactStatus: TypeAlias = Literal["planned", "available", "recorded", "future"]


@dataclass(frozen=True, slots=True)
class EvolutionArtifactRef:
    artifact_id: str
    kind: str
    owner: EvolutionArtifactOwner
    notes: str = ""


def dedupe_artifact_refs(
    refs: Iterable[EvolutionArtifactRef],
) -> tuple[EvolutionArtifactRef, ...]:
    deduped: list[EvolutionArtifactRef] = []
    seen: set[tuple[str, str, str, str]] = set()
    for ref in refs:
        key = (ref.artifact_id, ref.kind, ref.owner, ref.notes)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(ref)
    return tuple(deduped)


@dataclass(frozen=True, slots=True, kw_only=True)
class _EvolutionArtifact:
    artifact_id: str
    producing_stage: str
    status: EvolutionArtifactStatus
    depends_on: tuple[EvolutionArtifactRef, ...] = ()
    evidence_refs: tuple[EvolutionArtifactRef, ...] = ()
    persisted: bool = False

    kind: ClassVar[str]
    owner: ClassVar[EvolutionArtifactOwner]

    def to_ref(self, notes: str = "") -> EvolutionArtifactRef:
        return EvolutionArtifactRef(
            artifact_id=self.artifact_id,
            kind=self.kind,
            owner=self.owner,
            notes=notes,
        )


@dataclass(frozen=True, slots=True)
class EvolutionRunSpec(_EvolutionArtifact):
    kind: ClassVar[str] = EVOLUTION_ARTIFACT_KIND_RUN_SPEC
    owner: ClassVar[EvolutionArtifactOwner] = EVOLUTION_ARTIFACT_OWNER_EVOLUTION

    run_id: str
    repo_root: str
    selection_mode: str
    target_ids: tuple[str, ...]
    notes: str = ""


@dataclass(frozen=True, slots=True)
class EvolutionDatasetArtifact(_EvolutionArtifact):
    kind: ClassVar[str] = EVOLUTION_ARTIFACT_KIND_DATASET
    owner: ClassVar[EvolutionArtifactOwner] = EVOLUTION_ARTIFACT_OWNER_EVOLUTION

    run_id: str
    selected_task_ids: tuple[str, ...]
    task_count: int
    event_count: int
    trace_sources: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class EvolutionCandidateArtifact(_EvolutionArtifact):
    kind: ClassVar[str] = EVOLUTION_ARTIFACT_KIND_CANDIDATE
    owner: ClassVar[EvolutionArtifactOwner] = EVOLUTION_ARTIFACT_OWNER_EVOLUTION

    run_id: str
    candidate_id: str
    candidate_role: str
    target_ids: tuple[str, ...]
    change_summary: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class EvolutionEvaluationArtifact(_EvolutionArtifact):
    kind: ClassVar[str] = EVOLUTION_ARTIFACT_KIND_EVALUATION
    owner: ClassVar[EvolutionArtifactOwner] = EVOLUTION_ARTIFACT_OWNER_EVOLUTION

    run_id: str
    candidate_id: str
    evaluation_scope: str
    metric_fields: tuple[str, ...]
    summary_lines: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class EvolutionReportArtifact(_EvolutionArtifact):
    kind: ClassVar[str] = EVOLUTION_ARTIFACT_KIND_REPORT
    owner: ClassVar[EvolutionArtifactOwner] = EVOLUTION_ARTIFACT_OWNER_EVOLUTION

    run_id: str
    headline: str
    recommendation: str
    comparison_summary: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class EvolutionFollowupRequestArtifact(_EvolutionArtifact):
    kind: ClassVar[str] = EVOLUTION_ARTIFACT_KIND_FOLLOWUP_REQUEST
    owner: ClassVar[EvolutionArtifactOwner] = EVOLUTION_ARTIFACT_OWNER_EVOLUTION

    run_id: str
    candidate_id: str
    title: str
    summary: str
    requested_task_type: str
    requested_targets: tuple[str, ...]
    required_review_gates: tuple[str, ...]
    followup_task_id: str | None = None


@dataclass(frozen=True, slots=True)
class ExecutionReceiptArtifact(_EvolutionArtifact):
    kind: ClassVar[str] = EVOLUTION_ARTIFACT_KIND_EXECUTION_RECEIPT
    owner: ClassVar[EvolutionArtifactOwner] = EVOLUTION_ARTIFACT_OWNER_SISYPHUS

    run_id: str
    task_id: str
    receipt_kind: str
    receipt_locator: str


@dataclass(frozen=True, slots=True)
class VerificationArtifact(_EvolutionArtifact):
    kind: ClassVar[str] = EVOLUTION_ARTIFACT_KIND_VERIFICATION
    owner: ClassVar[EvolutionArtifactOwner] = EVOLUTION_ARTIFACT_OWNER_SISYPHUS

    run_id: str
    claim: str
    verification_method: str
    verification_scope: str
    result: str


@dataclass(frozen=True, slots=True)
class PromotionDecisionArtifact(_EvolutionArtifact):
    kind: ClassVar[str] = EVOLUTION_ARTIFACT_KIND_PROMOTION_DECISION
    owner: ClassVar[EvolutionArtifactOwner] = EVOLUTION_ARTIFACT_OWNER_SISYPHUS

    run_id: str
    candidate_id: str
    decision: str
    claim: str
    followup_task_id: str | None = None
    blocker_details: tuple[str, ...] = ()
