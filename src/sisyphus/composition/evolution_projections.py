from __future__ import annotations

from pathlib import Path

from ..evolution.receipts import (
    EvolutionFollowupExecutionProjection,
    project_followup_execution_from_ports,
)
from ..evolution.verification import (
    EvolutionFollowupVerificationProjection,
    project_followup_verification_from_ports,
)
from ..infra.config.loader import SisyphusConfig
from ..infra.evolution import RepositoryEvolutionEvents, RepositoryEvolutionTaskQueries


def project_followup_execution(
    repo_root: Path,
    config: SisyphusConfig,
    task_id: str,
) -> EvolutionFollowupExecutionProjection:
    return project_followup_execution_from_ports(
        RepositoryEvolutionTaskQueries(repo_root, config),
        RepositoryEvolutionEvents(repo_root, config),
        task_id,
    )


def project_followup_verification(
    repo_root: Path,
    config: SisyphusConfig,
    task_id: str,
) -> EvolutionFollowupVerificationProjection:
    return project_followup_verification_from_ports(
        RepositoryEvolutionTaskQueries(repo_root, config),
        RepositoryEvolutionEvents(repo_root, config),
        task_id,
    )


__all__ = ["project_followup_execution", "project_followup_verification"]
