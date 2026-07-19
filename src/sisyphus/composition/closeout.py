from __future__ import annotations

from pathlib import Path

from ..application.results.closeout import CloseOutcome
from ..application.use_cases.closeout import CloseoutService
from ..infra.clock import SystemClock
from ..infra.closeout import (
    GitWorktreeStatusAdapter,
    RepositoryCloseoutEvidenceAdapter,
    is_dirty_worktree,
)
from ..infra.closeout.git_status import DirtyChecker
from ..infra.config.loader import SisyphusConfig
from ..infra.orchestration.common_adapters import (
    EventPublisherAdapter,
    FileTaskRecordAdapter,
    ManualInterventionAdapter,
)


def build_closeout_service(
    repo_root: Path,
    config: SisyphusConfig,
    *,
    dirty_checker: DirtyChecker = is_dirty_worktree,
) -> CloseoutService:
    clock = SystemClock()
    return CloseoutService(
        tasks=FileTaskRecordAdapter(repo_root, config),
        evidence=RepositoryCloseoutEvidenceAdapter(repo_root, config, clock),
        worktree=GitWorktreeStatusAdapter(repo_root, dirty_checker),
        events=EventPublisherAdapter(repo_root, config),
        interventions=ManualInterventionAdapter(repo_root, config),
        clock=clock,
    )


def close_task(
    repo_root: Path,
    config: SisyphusConfig,
    task_id: str,
    allow_dirty: bool,
) -> CloseOutcome:
    return build_closeout_service(repo_root, config).close(
        task_id,
        allow_dirty=allow_dirty,
    )


__all__ = ["build_closeout_service", "close_task"]
