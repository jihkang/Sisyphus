from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re

from ..api import request_task
from ..config import SisyphusConfig
from ..utils import optional_str
from .artifacts import EVOLUTION_ARTIFACT_STATUS_RECORDED, EvolutionFollowupRequestArtifact
from .event_bus import EVOLUTION_EVENT_FOLLOWUP_REQUESTED, publish_evolution_event
from .followup import EVOLUTION_FOLLOWUP_SOURCE_CONTEXT_KIND
from .handoff import (
    EVOLUTION_DEFAULT_REVIEW_GATES,
    EVOLUTION_PROMOTION_INTENT_REQUEST_FOLLOWUP,
    EvolutionEvidenceSummary,
    EvolutionFollowupRequest,
    EvolutionReviewGate,
    EvolutionVerificationObligation,
)
EVOLUTION_FOLLOWUP_PROHIBITED_FLAGS = (
    "permits_plan_approval",
    "permits_spec_freeze",
    "permits_execution",
    "permits_promotion",
)


@dataclass(frozen=True, slots=True)
class EvolutionBridgedFollowupTask:
    task_id: str
    slug: str
    status: str | None
    plan_status: str | None
    spec_status: str | None
    workflow_phase: str | None
    owned_paths: tuple[str, ...]
    source_context: dict[str, object]
    artifact: EvolutionFollowupRequestArtifact


def bridge_evolution_followup_request(
    repo_root: Path,
    followup_request: EvolutionFollowupRequest,
    *,
    config: SisyphusConfig | None = None,
    slug: str | None = None,
) -> EvolutionBridgedFollowupTask:
    _validate_followup_request(followup_request)

    normalized_owned_paths = _dedupe_strings(followup_request.owned_paths)
    normalized_review_gates = _normalize_review_gates(followup_request.required_review_gates)
    normalized_obligations = _normalize_verification_obligations(
        followup_request.expected_verification_obligations
    )
    normalized_evidence = _normalize_evidence_summary(followup_request.evidence_summary)
    artifact_id = _followup_artifact_id(followup_request)
    normalized_slug = slug or _slugify(
        followup_request.title,
        fallback=f"{followup_request.candidate_id}-followup",
    )
    source_context = _build_followup_source_context(
        followup_request=followup_request,
        artifact_id=artifact_id,
        review_gates=normalized_review_gates,
        obligations=normalized_obligations,
        evidence_summary=normalized_evidence,
    )

    result = request_task(
        repo_root=repo_root,
        config=config,
        message=followup_request.summary,
        title=followup_request.title,
        task_type=followup_request.requested_task_type,
        slug=normalized_slug,
        instruction=_render_followup_instruction(followup_request),
        owned_paths=list(normalized_owned_paths),
        source_context=source_context,
        auto_run=False,
    )
    if not result.ok or not result.task_id or not result.task:
        raise RuntimeError(result.error or "failed to create evolution follow-up task")

    task = result.task
    artifact = EvolutionFollowupRequestArtifact(
        artifact_id=artifact_id,
        producing_stage="followup_requested",
        status=EVOLUTION_ARTIFACT_STATUS_RECORDED,
        run_id=followup_request.source_run_id,
        candidate_id=followup_request.candidate_id,
        title=followup_request.title,
        summary=followup_request.summary,
        requested_task_type=followup_request.requested_task_type,
        requested_targets=tuple(_dedupe_strings(followup_request.target_scope)),
        required_review_gates=normalized_review_gates,
        followup_task_id=str(result.task_id),
    )
    publish_evolution_event(
        repo_root,
        config=config,
        event_type=EVOLUTION_EVENT_FOLLOWUP_REQUESTED,
        source_module="evolution.bridge",
        data={
            "run_id": artifact.run_id,
            "candidate_id": artifact.candidate_id,
            "followup_task_id": artifact.followup_task_id,
            "requested_task_type": artifact.requested_task_type,
            "requested_targets": list(artifact.requested_targets),
            "required_review_gates": list(artifact.required_review_gates),
        },
    )
    return EvolutionBridgedFollowupTask(
        task_id=str(result.task_id),
        slug=str(task.get("slug") or normalized_slug),
        status=optional_str(task.get("status")),
        plan_status=optional_str(task.get("plan_status")),
        spec_status=optional_str(task.get("spec_status")),
        workflow_phase=optional_str(task.get("workflow_phase")),
        owned_paths=normalized_owned_paths,
        source_context=source_context,
        artifact=artifact,
    )


def _validate_followup_request(followup_request: EvolutionFollowupRequest) -> None:
    if followup_request.requested_task_type not in {"feature", "issue"}:
        raise ValueError(
            f"unsupported follow-up task type: {followup_request.requested_task_type}"
        )
    if not followup_request.request_only:
        raise ValueError("follow-up bridge only supports request-only handoff")
    if followup_request.promotion_intent != EVOLUTION_PROMOTION_INTENT_REQUEST_FOLLOWUP:
        raise ValueError("follow-up bridge requires promotion_intent=request_followup")
    for field_name in EVOLUTION_FOLLOWUP_PROHIBITED_FLAGS:
        if getattr(followup_request, field_name):
            raise ValueError(
                f"follow-up bridge forbids privileged handoff flag: {field_name}"
            )
    if not _dedupe_strings(followup_request.target_scope):
        raise ValueError("follow-up bridge requires at least one target in scope")
    if not followup_request.expected_verification_obligations:
        raise ValueError("follow-up bridge requires verification obligations")
    if not followup_request.evidence_summary:
        raise ValueError("follow-up bridge requires evidence summaries")
    if not str(followup_request.title).strip():
        raise ValueError("follow-up bridge requires a non-empty title")
    if not str(followup_request.summary).strip():
        raise ValueError("follow-up bridge requires a non-empty summary")


def _normalize_review_gates(
    review_gates: tuple[EvolutionReviewGate, ...],
) -> tuple[EvolutionReviewGate, ...]:
    if not review_gates:
        raise ValueError("follow-up bridge requires review gates")
    allowed = set(EVOLUTION_DEFAULT_REVIEW_GATES)
    normalized: list[EvolutionReviewGate] = []
    seen: set[str] = set()
    for gate in review_gates:
        normalized_gate = str(gate).strip()
        if normalized_gate not in allowed:
            raise ValueError(f"unsupported review gate: {normalized_gate}")
        if normalized_gate in seen:
            continue
        seen.add(normalized_gate)
        normalized.append(normalized_gate)  # type: ignore[arg-type]
    if not normalized:
        raise ValueError("follow-up bridge requires review gates")
    return tuple(normalized)


def _normalize_verification_obligations(
    obligations: tuple[EvolutionVerificationObligation, ...],
) -> tuple[EvolutionVerificationObligation, ...]:
    normalized: list[EvolutionVerificationObligation] = []
    seen: set[tuple[str, str, bool]] = set()
    for obligation in obligations:
        claim = str(obligation.claim).strip()
        method = str(obligation.method).strip()
        if not claim or not method:
            raise ValueError("verification obligations require non-empty claim and method")
        key = (claim, method, bool(obligation.required))
        if key in seen:
            continue
        seen.add(key)
        normalized.append(
            EvolutionVerificationObligation(
                claim=claim,
                method=method,
                required=bool(obligation.required),
            )
        )
    if not normalized:
        raise ValueError("follow-up bridge requires verification obligations")
    return tuple(normalized)


def _normalize_evidence_summary(
    evidence_summary: tuple[EvolutionEvidenceSummary, ...],
) -> tuple[EvolutionEvidenceSummary, ...]:
    normalized: list[EvolutionEvidenceSummary] = []
    seen: set[tuple[str, str, str | None]] = set()
    for entry in evidence_summary:
        kind = str(entry.kind).strip()
        summary = str(entry.summary).strip()
        locator = optional_str(entry.locator)
        if not kind or not summary:
            raise ValueError("evidence summaries require non-empty kind and summary")
        key = (kind, summary, locator)
        if key in seen:
            continue
        seen.add(key)
        normalized.append(
            EvolutionEvidenceSummary(
                kind=kind,
                summary=summary,
                locator=locator,
            )
        )
    if not normalized:
        raise ValueError("follow-up bridge requires evidence summaries")
    return tuple(normalized)


def _build_followup_source_context(
    *,
    followup_request: EvolutionFollowupRequest,
    artifact_id: str,
    review_gates: tuple[EvolutionReviewGate, ...],
    obligations: tuple[EvolutionVerificationObligation, ...],
    evidence_summary: tuple[EvolutionEvidenceSummary, ...],
) -> dict[str, object]:
    return {
        EVOLUTION_FOLLOWUP_SOURCE_CONTEXT_KIND: {
            "artifact_id": artifact_id,
            "source_run_id": followup_request.source_run_id,
            "candidate_id": followup_request.candidate_id,
            "title": followup_request.title,
            "summary": followup_request.summary,
            "requested_task_type": followup_request.requested_task_type,
            "promotion_intent": followup_request.promotion_intent,
            "target_scope": list(_dedupe_strings(followup_request.target_scope)),
            "required_review_gates": list(review_gates),
            "request_only": True,
            "expected_verification_obligations": [
                {
                    "claim": obligation.claim,
                    "method": obligation.method,
                    "required": obligation.required,
                }
                for obligation in obligations
            ],
            "evidence_summary": [
                {
                    "kind": entry.kind,
                    "summary": entry.summary,
                    "locator": entry.locator,
                }
                for entry in evidence_summary
            ],
        }
    }


def _render_followup_instruction(
    followup_request: EvolutionFollowupRequest,
) -> str | None:
    instructions = tuple(
        instruction.strip()
        for instruction in followup_request.instruction_set
        if instruction.strip()
    )
    if not instructions:
        return None
    lines = [
        "Implement the reviewed evolution follow-up through the normal Sisyphus lifecycle.",
        "Do not bypass plan review, operator approval, spec freeze, verify, or receipt recording.",
        "",
        "Instructions:",
    ]
    lines.extend(f"- {instruction}" for instruction in instructions)
    return "\n".join(lines)


def _followup_artifact_id(followup_request: EvolutionFollowupRequest) -> str:
    run_id = _slugify(followup_request.source_run_id, fallback="run")
    candidate_id = _slugify(followup_request.candidate_id, fallback="candidate")
    return f"{run_id}-{candidate_id}-followup-request"


def _dedupe_strings(values: tuple[str, ...] | list[str]) -> tuple[str, ...]:
    normalized: list[str] = []
    seen: set[str] = set()
    for value in values:
        normalized_value = str(value).strip()
        if not normalized_value or normalized_value in seen:
            continue
        seen.add(normalized_value)
        normalized.append(normalized_value)
    return tuple(normalized)


def _slugify(value: str, *, fallback: str) -> str:
    lowered = re.sub(r"[^a-z0-9]+", "-", value.strip().lower()).strip("-")
    return lowered or fallback
