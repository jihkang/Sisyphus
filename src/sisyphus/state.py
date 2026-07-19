from __future__ import annotations

from pathlib import Path

from .application.commands.task import CreateTaskRecordCommand
from .composition.task_creation import build_task_record_creation_service
from .config import SisyphusConfig
from .domain.task.models import DEFAULT_CHANGESET_PATH, DEFAULT_PROMOTION_RECEIPT_PATH
from .infra.orchestration.task_factory import build_task_record, task_id_for
from .infra.persistence.task_repository import (
    ConcurrentTaskUpdateError,
    ensure_task_record_defaults,
    list_task_records,
    load_task_record,
    normalize_task_projection,
    save_task_record,
    sync_task_support_files,
    update_task_record,
)
from .shared.clock import utc_now


def create_task_record(
    repo_root: Path,
    config: SisyphusConfig,
    task_type: str,
    slug: str,
) -> dict:
    return build_task_record_creation_service(repo_root, config).create(
        CreateTaskRecordCommand(
            task_type=task_type,
            slug=slug,
        )
    )
