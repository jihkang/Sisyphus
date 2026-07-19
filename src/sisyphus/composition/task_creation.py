from __future__ import annotations

from pathlib import Path

from ..application.use_cases.task_creation import TaskRecordCreationService
from ..infra.config.loader import SisyphusConfig
from ..infra.orchestration.task_factory import RepositoryTaskFactoryAdapter
from ..infra.persistence.task_records import FileTaskRecordAdapter


def build_task_record_creation_service(
    repo_root: Path,
    config: SisyphusConfig,
) -> TaskRecordCreationService:
    return TaskRecordCreationService(
        factory=RepositoryTaskFactoryAdapter(repo_root, config),
        tasks=FileTaskRecordAdapter(repo_root, config),
    )


__all__ = ["build_task_record_creation_service"]
