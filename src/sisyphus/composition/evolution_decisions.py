from __future__ import annotations

from pathlib import Path

from ..evolution.promotion import (
    EvolutionDecisionEnvelope,
    EvolutionPromotionGateResult,
    record_evolution_decision_envelope as record_decision,
)
from ..infra.config.loader import SisyphusConfig, load_config
from ..infra.evolution import RepositoryEvolutionEvents


def record_evolution_decision_envelope(
    gate_result: EvolutionPromotionGateResult,
    *,
    claim: str,
    repo_root: Path | None = None,
    config: SisyphusConfig | None = None,
) -> EvolutionDecisionEnvelope:
    if repo_root is None:
        return record_decision(gate_result, claim=claim)
    resolved_root = repo_root.resolve()
    resolved_config = config or load_config(resolved_root)
    return record_decision(
        gate_result,
        claim=claim,
        events=RepositoryEvolutionEvents(resolved_root, resolved_config),
    )


__all__ = ["record_evolution_decision_envelope"]
