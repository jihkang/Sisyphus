from __future__ import annotations

from pathlib import Path

from ..application.use_cases.promotion import PromotionService
from ..infra.artifacts import RepositoryArtifactStore
from ..infra.clock import SystemClock
from ..infra.config.loader import SisyphusConfig
from ..infra.orchestration.common_adapters import (
    FileTaskRecordAdapter,
    ManualInterventionAdapter,
    ReopenedTaskAdapter,
)
from ..infra.orchestration.workflow_adapters import CloseoutAdapter
from ..infra.promotion import GhRunner, GitVersionControlAdapter, GithubCliPullRequestAdapter
from ..infra.verification import ConformanceVerificationAdapter


def build_promotion_service(
    repo_root: Path,
    config: SisyphusConfig,
    *,
    gh_runner: GhRunner,
) -> PromotionService:
    return PromotionService(
        tasks=FileTaskRecordAdapter(repo_root, config),
        version_control=GitVersionControlAdapter(),
        pull_requests=GithubCliPullRequestAdapter(gh_runner),
        artifacts=RepositoryArtifactStore(repo_root, config),
        conformance=ConformanceVerificationAdapter(),
        closeout=CloseoutAdapter(repo_root, config),
        interventions=ManualInterventionAdapter(repo_root, config),
        reopened_tasks=ReopenedTaskAdapter(repo_root, config),
        clock=SystemClock(),
    )


__all__ = ["build_promotion_service"]
