from __future__ import annotations

from pathlib import Path

from .config import SisyphusConfig
from .domain.task.factory import build_task_record, task_id_for
from .domain.task.models import DEFAULT_CHANGESET_PATH, DEFAULT_PROMOTION_RECEIPT_PATH
from .domain.task.repository import (
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
    task = build_task_record(
        repo_root=repo_root,
        config=config,
        task_type=task_type,
        slug=slug,
    )
    task_path = repo_root / task["task_dir"]
    task_path.mkdir(parents=True, exist_ok=True)
    task_file = task_path / "task.json"
    save_task_record(task_file=task_file, task=task)
    return task
