from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace

from ..shared.coerce import optional_str, required_str
from .artifacts import EVOLUTION_ARTIFACT_STATUS_RECORDED, EvolutionFollowupRequestArtifact
from .bridge import EvolutionBridgedFollowupTask
from .followup import EVOLUTION_FOLLOWUP_SOURCE_CONTEXT_KIND, extract_followup_source_context
from .handoff import (
    EVOLUTION_DEFAULT_REVIEW_GATES,
    EVOLUTION_PROMOTION_INTENT_REQUEST_FOLLOWUP,
    EvolutionEvidenceSummary,
    EvolutionFollowupRequest,
    EvolutionReviewGate,
    EvolutionVerificationObligation,
)
from .promotion import (
    EvolutionDecisionEnvelope,
    EvolutionPromotionGateResult,
    evaluate_evolution_promotion_gate,
)
from .receipts import EvolutionFollowupExecutionProjection
from .presentation import EvolutionRunArtifacts
from .verification import EvolutionFollowupVerificationProjection


@dataclass(frozen=True, slots=True)
class EvolutionFollowupSurfaceResult:
    task_id: str
    task_uri: str
    run_id: str
    candidate_id: str
    content: str
    requested_targets: tuple[str, ...]
    required_review_gates: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class EvolutionDecisionSurfaceResult:
    task_id: str
    task_uri: str
    run_id: str
    candidate_id: str
    gate_status: str
    envelope_status: str
    content: str
    gate_result: EvolutionPromotionGateResult
    envelope: EvolutionDecisionEnvelope


def request_evolution_followup_with_services(
    repo_root: Path,
    *,
    run_id: str,
    candidate_id: str,
    title: str,
    summary: str,
    requested_task_type: str = "feature",
    slug: str | None = None,
    target_ids: Sequence[str] | None = None,
    owned_paths: Sequence[str] | None = None,
    review_gates: Sequence[str] | None = None,
    verification_obligations: Sequence[EvolutionVerificationObligation] | None = None,
    evidence_summary: Sequence[EvolutionEvidenceSummary] | None = None,
    load_artifacts: Callable[[str], EvolutionRunArtifacts],
    bridge_followup: Callable[[EvolutionFollowupRequest, str | None], EvolutionBridgedFollowupTask],
) -> EvolutionFollowupSurfaceResult:
    resolved_repo_root = repo_root.resolve()
    artifacts = load_artifacts(run_id)
    normalized_targets = _normalize_strings(target_ids) or artifacts.target_ids
    if not normalized_targets:
        raise ValueError("evolution follow-up request requires at least one target id")

    request = EvolutionFollowupRequest(
        source_run_id=run_id,
        candidate_id=required_str(candidate_id, "candidate_id"),
        title=required_str(title, "title"),
        summary=required_str(summary, "summary"),
        requested_task_type=requested_task_type,
        target_scope=normalized_targets,
        instruction_set=(),
        owned_paths=_normalize_strings(owned_paths),
        expected_verification_obligations=_normalize_verification_obligations(
            verification_obligations,
            run_id=run_id,
            candidate_id=candidate_id,
        ),
        evidence_summary=_normalize_evidence_summary(
            evidence_summary,
            artifacts=artifacts,
            repo_root=resolved_repo_root,
        ),
        promotion_intent=EVOLUTION_PROMOTION_INTENT_REQUEST_FOLLOWUP,
        required_review_gates=_normalize_review_gates(review_gates),
    )
    bridged = bridge_followup(request, slug)
    return EvolutionFollowupSurfaceResult(
        task_id=bridged.task_id,
        task_uri=_task_record_uri(bridged.task_id),
        run_id=bridged.artifact.run_id,
        candidate_id=bridged.artifact.candidate_id,
        content=_render_followup_request_content(bridged),
        requested_targets=bridged.artifact.requested_targets,
        required_review_gates=bridged.artifact.required_review_gates,
    )


def evaluate_evolution_followup_decision_with_services(
    task: Mapping[str, object],
    *,
    task_id: str,
    claim: str | None = None,
    load_artifacts: Callable[[str], EvolutionRunArtifacts],
    project_execution: Callable[[str], EvolutionFollowupExecutionProjection],
    project_verification: Callable[[str], EvolutionFollowupVerificationProjection],
    record_decision: Callable[[EvolutionPromotionGateResult, str], EvolutionDecisionEnvelope],
) -> EvolutionDecisionSurfaceResult:
    followup_request = project_followup_request_artifact(task)
    run_artifacts = load_artifacts(followup_request.run_id)
    constraints = _project_constraint_result(run_artifacts)
    fitness = _project_fitness_result(run_artifacts)
    execution_projection = _maybe_project_execution(
        task,
        project_execution=project_execution,
    )
    verification_projection = _maybe_project_verification(
        task,
        execution_projection=execution_projection,
        project_verification=project_verification,
    )
    gate_result = evaluate_evolution_promotion_gate(
        followup_request,
        constraints=constraints,
        fitness=fitness,
        execution_projection=execution_projection,
        verification_projection=verification_projection,
    )
    decision_claim = claim or (
        f"follow-up task {task_id} satisfies review-gated promotion policy for "
        f"{followup_request.candidate_id}"
    )
    envelope = record_decision(gate_result, decision_claim)
    return EvolutionDecisionSurfaceResult(
        task_id=task_id,
        task_uri=_task_record_uri(task_id),
        run_id=followup_request.run_id,
        candidate_id=followup_request.candidate_id,
        gate_status=gate_result.status,
        envelope_status=envelope.status,
        content=_render_decision_content(
            task_id=task_id,
            gate_result=gate_result,
            envelope=envelope,
        ),
        gate_result=gate_result,
        envelope=envelope,
    )


def project_followup_request_artifact(task: Mapping[str, object]) -> EvolutionFollowupRequestArtifact:
    source_context = extract_followup_source_context(task, purpose="follow-up projection")
    task_id = optional_str(task.get("id"))
    run_id = required_str(source_context.get("source_run_id"), "source_context.source_run_id")
    candidate_id = required_str(source_context.get("candidate_id"), "source_context.candidate_id")
    requested_targets = _normalize_strings(source_context.get("target_scope"))
    required_review_gates = _normalize_review_gates(source_context.get("required_review_gates"))
    artifact_id = optional_str(source_context.get("artifact_id")) or _fallback_followup_artifact_id(
        run_id=run_id,
        candidate_id=candidate_id,
    )
    title = optional_str(source_context.get("title")) or task_id or f"{candidate_id}-followup"
    summary = optional_str(source_context.get("summary")) or f"Evolution follow-up task {task_id or candidate_id}"
    requested_task_type = optional_str(source_context.get("requested_task_type")) or required_str(
        task.get("type"),
        "task.type",
    )
    return EvolutionFollowupRequestArtifact(
        artifact_id=artifact_id,
        producing_stage="followup_requested",
        status=EVOLUTION_ARTIFACT_STATUS_RECORDED,
        run_id=run_id,
        candidate_id=candidate_id,
        title=title,
        summary=summary,
        requested_task_type=requested_task_type,
        requested_targets=requested_targets,
        required_review_gates=required_review_gates,
        followup_task_id=task_id,
    )


def _normalize_review_gates(review_gates: object) -> tuple[EvolutionReviewGate, ...]:
    if review_gates is None:
        return EVOLUTION_DEFAULT_REVIEW_GATES
    normalized = _normalize_strings(review_gates)
    if not normalized:
        return EVOLUTION_DEFAULT_REVIEW_GATES
    allowed = set(EVOLUTION_DEFAULT_REVIEW_GATES)
    invalid = [gate for gate in normalized if gate not in allowed]
    if invalid:
        raise ValueError(f"unsupported review gate(s): {', '.join(invalid)}")
    return tuple(normalized)  # type: ignore[return-value]


def _normalize_verification_obligations(
    verification_obligations: Sequence[EvolutionVerificationObligation] | None,
    *,
    run_id: str,
    candidate_id: str,
) -> tuple[EvolutionVerificationObligation, ...]:
    if not verification_obligations:
        return (
            EvolutionVerificationObligation(
                claim=f"follow-up task preserves reviewed evolution intent for {run_id}/{candidate_id}",
                method="sisyphus verify",
            ),
        )
    normalized: list[EvolutionVerificationObligation] = []
    seen: set[tuple[str, str, bool]] = set()
    for obligation in verification_obligations:
        claim = str(obligation.claim).strip()
        method = str(obligation.method).strip()
        key = (claim, method, bool(obligation.required))
        if not claim or not method or key in seen:
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
        raise ValueError("verification obligations require at least one non-empty entry")
    return tuple(normalized)


def _normalize_evidence_summary(
    evidence_summary: Sequence[EvolutionEvidenceSummary] | None,
    *,
    artifacts: EvolutionRunArtifacts,
    repo_root: Path,
) -> tuple[EvolutionEvidenceSummary, ...]:
    if not evidence_summary:
        report_locator = None
        artifact_dir = Path(artifacts.artifact_dir)
        report_path = artifact_dir / "report.md"
        if "report.md" in artifacts.available_artifacts:
            report_locator = report_path.relative_to(repo_root).as_posix()
        return (
            EvolutionEvidenceSummary(
                kind="evolution_report",
                summary=f"follow-up requested from evolution run {artifacts.run_id}",
                locator=report_locator,
            ),
        )
    normalized: list[EvolutionEvidenceSummary] = []
    seen: set[tuple[str, str, str | None]] = set()
    for item in evidence_summary:
        kind = str(item.kind).strip()
        summary = str(item.summary).strip()
        locator = optional_str(item.locator)
        key = (kind, summary, locator)
        if not kind or not summary or key in seen:
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
        raise ValueError("evidence summaries require at least one non-empty entry")
    return tuple(normalized)


def _project_constraint_result(
    artifacts: EvolutionRunArtifacts,
) -> SimpleNamespace | None:
    payload = artifacts.constraints
    if payload is None:
        return None
    accepted = payload.get("accepted")
    if not isinstance(accepted, bool):
        accepted = None
    return SimpleNamespace(
        status=optional_str(payload.get("status")) or "pending",
        accepted=accepted,
        notes=optional_str(payload.get("notes")) or "constraint status projected from run artifacts",
    )


def _project_fitness_result(
    artifacts: EvolutionRunArtifacts,
) -> SimpleNamespace | None:
    payload = artifacts.fitness
    if payload is None:
        return None
    eligible = payload.get("eligible_for_promotion")
    if not isinstance(eligible, bool):
        eligible = None
    return SimpleNamespace(
        status=optional_str(payload.get("status")) or "pending",
        eligible_for_promotion=eligible,
        notes=optional_str(payload.get("notes")) or "fitness status projected from run artifacts",
    )


def _maybe_project_execution(
    task: Mapping[str, object],
    *,
    project_execution: Callable[[str], EvolutionFollowupExecutionProjection],
) -> EvolutionFollowupExecutionProjection | None:
    if not _should_project_execution(task):
        return None
    task_id = required_str(task.get("id"), "task.id")
    return project_execution(task_id)


def _maybe_project_verification(
    task: Mapping[str, object],
    *,
    execution_projection: EvolutionFollowupExecutionProjection | None,
    project_verification: Callable[[str], EvolutionFollowupVerificationProjection],
) -> EvolutionFollowupVerificationProjection | None:
    if execution_projection is None or not _should_project_execution(task):
        return None
    task_id = required_str(task.get("id"), "task.id")
    return project_verification(task_id)


def _should_project_execution(task: Mapping[str, object]) -> bool:
    verify_status = optional_str(task.get("verify_status"))
    if verify_status in {"passed", "failed"}:
        return True
    verify_results = task.get("last_verify_results")
    return isinstance(verify_results, Sequence) and not isinstance(verify_results, (str, bytes)) and bool(verify_results)


def _normalize_strings(values: object) -> tuple[str, ...]:
    if values is None:
        return ()
    if isinstance(values, (str, bytes)):
        normalized = str(values).strip()
        return (normalized,) if normalized else ()
    if not isinstance(values, Sequence):
        return ()
    deduped: list[str] = []
    seen: set[str] = set()
    for value in values:
        normalized = str(value).strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        deduped.append(normalized)
    return tuple(deduped)


def _task_record_uri(task_id: str) -> str:
    return f"task://{task_id}/record"


def _render_followup_request_content(result) -> str:
    lines = [
        f"evolution followup request {result.artifact.run_id} {result.artifact.candidate_id}",
        f"followup_task_id: {result.task_id}",
        f"task_uri: {_task_record_uri(result.task_id)}",
        f"status: {result.status or 'unknown'}",
        f"plan_status: {result.plan_status or 'unknown'}",
        f"spec_status: {result.spec_status or 'unknown'}",
        f"workflow_phase: {result.workflow_phase or 'unknown'}",
        f"requested_targets: {', '.join(result.artifact.requested_targets) or 'none'}",
        f"required_review_gates: {', '.join(result.artifact.required_review_gates) or 'none'}",
    ]
    return "\n".join(lines) + "\n"


def _render_decision_content(
    *,
    task_id: str,
    gate_result: EvolutionPromotionGateResult,
    envelope: EvolutionDecisionEnvelope,
) -> str:
    lines = [
        f"evolution decision {task_id}",
        f"task_uri: {_task_record_uri(task_id)}",
        f"run_id: {gate_result.run_id}",
        f"candidate_id: {gate_result.candidate_id}",
        f"gate_status: {gate_result.status}",
        f"envelope_status: {envelope.status}",
        f"followup_task_id: {gate_result.followup_task_id or task_id}",
        f"required_review_gates: {', '.join(gate_result.required_review_gates) or 'none'}",
        f"blocking_conditions: {len(gate_result.blocking_conditions)}",
        f"evidence_refs: {len(envelope.evidence_refs)}",
    ]
    for blocker in gate_result.blocking_conditions:
        lines.append(f"- {blocker.blocker_id}: {blocker.detail}")
    return "\n".join(lines) + "\n"


def _fallback_followup_artifact_id(*, run_id: str, candidate_id: str) -> str:
    normalized_run = run_id.strip().lower().replace("_", "-")
    normalized_candidate = candidate_id.strip().lower().replace("_", "-")
    normalized_run = "".join(char if char.isalnum() or char == "-" else "-" for char in normalized_run)
    normalized_candidate = "".join(
        char if char.isalnum() or char == "-" else "-" for char in normalized_candidate
    )
    return f"artifact-{normalized_run}-{normalized_candidate}-followup-request"
