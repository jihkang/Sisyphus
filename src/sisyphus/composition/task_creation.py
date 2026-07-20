from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from ..application.use_cases.task_creation import (
    TaskRecordCreationService,
    TaskWorkspaceCreationService,
)
from ..infra.config.loader import SisyphusConfig
from ..infra.orchestration.task_factory import RepositoryTaskFactoryAdapter
from ..infra.persistence.task_records import FileTaskRecordAdapter
from ..infra.task_creation import RepositoryTaskTemplateAdapter, RepositoryTaskWorkspaceAdapter


def build_task_record_creation_service(
    repo_root: Path,
    config: SisyphusConfig,
) -> TaskRecordCreationService:
    return TaskRecordCreationService(
        factory=RepositoryTaskFactoryAdapter(repo_root, config),
        tasks=FileTaskRecordAdapter(repo_root, config),
    )


def build_task_workspace_creation_service(
    repo_root: Path,
    config: SisyphusConfig,
    *,
    template_materializer: Callable[[dict], None],
) -> TaskWorkspaceCreationService:
    return TaskWorkspaceCreationService(
        factory=RepositoryTaskFactoryAdapter(repo_root, config),
        tasks=FileTaskRecordAdapter(repo_root, config),
        workspace=RepositoryTaskWorkspaceAdapter(repo_root),
        templates=RepositoryTaskTemplateAdapter(template_materializer),
    )


__all__ = ["build_task_record_creation_service", "build_task_workspace_creation_service"]
