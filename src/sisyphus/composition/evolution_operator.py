from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from ..evolution.handoff import EvolutionEvidenceSummary, EvolutionVerificationObligation
from ..evolution.operator import (
    EvolutionDecisionSurfaceResult,
    EvolutionFollowupSurfaceResult,
    evaluate_evolution_followup_decision_with_services,
    request_evolution_followup_with_services,
)
from ..infra.config.loader import SisyphusConfig, load_config
from ..infra.evolution import RepositoryEvolutionTaskQueries
from .evolution_decisions import record_evolution_decision_envelope
from .evolution_followups import bridge_evolution_followup_request
from .evolution_projections import project_followup_execution, project_followup_verification
from .evolution_surface import load_evolution_run_artifacts


def request_evolution_followup(
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
    config: SisyphusConfig | None = None,
) -> EvolutionFollowupSurfaceResult:
    resolved_root = repo_root.resolve()
    resolved_config = config or load_config(resolved_root)
    return request_evolution_followup_with_services(
        resolved_root,
        run_id=run_id,
        candidate_id=candidate_id,
        title=title,
        summary=summary,
        requested_task_type=requested_task_type,
        slug=slug,
        target_ids=target_ids,
        owned_paths=owned_paths,
        review_gates=review_gates,
        verification_obligations=verification_obligations,
        evidence_summary=evidence_summary,
        load_artifacts=lambda selected_run_id: load_evolution_run_artifacts(
            resolved_root,
            selected_run_id,
        ),
        bridge_followup=lambda request, selected_slug: bridge_evolution_followup_request(
            resolved_root,
            request,
            config=resolved_config,
            slug=selected_slug,
        ),
    )


def evaluate_evolution_followup_decision(
    repo_root: Path,
    *,
    task_id: str,
    claim: str | None = None,
    config: SisyphusConfig | None = None,
) -> EvolutionDecisionSurfaceResult:
    resolved_root = repo_root.resolve()
    resolved_config = config or load_config(resolved_root)
    task, _ = RepositoryEvolutionTaskQueries(resolved_root, resolved_config).load_with_path(task_id)
    return evaluate_evolution_followup_decision_with_services(
        task,
        task_id=task_id,
        claim=claim,
        load_artifacts=lambda run_id: load_evolution_run_artifacts(resolved_root, run_id),
        project_execution=lambda selected_task_id: project_followup_execution(
            resolved_root,
            resolved_config,
            selected_task_id,
        ),
        project_verification=lambda selected_task_id: project_followup_verification(
            resolved_root,
            resolved_config,
            selected_task_id,
        ),
        record_decision=lambda gate, decision_claim: record_evolution_decision_envelope(
            gate,
            claim=decision_claim,
            repo_root=resolved_root,
            config=resolved_config,
        ),
    )


__all__ = ["evaluate_evolution_followup_decision", "request_evolution_followup"]
