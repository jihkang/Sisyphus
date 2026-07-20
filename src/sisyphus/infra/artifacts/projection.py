from __future__ import annotations

from pathlib import Path, PurePosixPath

from ...application.artifacts.projection import (
    FeatureTaskArtifactProjection,
    project_feature_task_data,
)
from ...domain.task.strategy import sync_test_strategy_from_content
from ..config.loader import SisyphusConfig
from ..persistence.task_repository import load_task_record
from ..workspace.secure_files import SecureWorkspaceFiles


_MAX_TASK_DOCUMENT_BYTES = 8 * 1024 * 1024


def project_feature_task(
    repo_root: Path,
    config: SisyphusConfig,
    task_id: str,
) -> FeatureTaskArtifactProjection:
    task, task_file = load_task_record(
        repo_root=repo_root,
        task_dir_name=config.task_dir,
        task_id=task_id,
    )
    return project_feature_task_record(task=task, task_dir=task_file.parent)


def project_feature_task_record(
    task: dict,
    task_dir: Path,
) -> FeatureTaskArtifactProjection:
    if task.get("type") != "feature":
        raise ValueError(
            f"feature task projection supports only feature tasks, got {task.get('type')!r}"
        )
    files = SecureWorkspaceFiles(task_dir)
    synced_task = _sync_test_strategy(task, files)
    brief_relative = _required_doc_path(synced_task, "brief")
    plan_relative = _required_doc_path(synced_task, "plan")
    return project_feature_task_data(
        synced_task,
        brief_path=brief_relative.as_posix(),
        brief_content=_read_required_document(files, brief_relative),
        plan_path=plan_relative.as_posix(),
        plan_content=_read_required_document(files, plan_relative),
    )


def _sync_test_strategy(task: dict, files: SecureWorkspaceFiles) -> dict:
    source = PurePosixPath("PLAN.md" if task.get("type") == "feature" else "FIX_PLAN.md")
    try:
        content = files.read_text(source, max_bytes=_MAX_TASK_DOCUMENT_BYTES)
    except FileNotFoundError:
        return dict(task)
    return sync_test_strategy_from_content(dict(task), content)


def _required_doc_path(task: dict, doc_key: str) -> PurePosixPath:
    value = task.get("docs", {}).get(doc_key)
    if not value:
        raise ValueError(f"feature task projection requires docs.{doc_key}")
    path = PurePosixPath(str(value))
    if path.is_absolute() or not path.parts or any(part in {"", ".", ".."} for part in path.parts):
        raise ValueError(f"feature task projection requires a contained docs.{doc_key} path")
    return path


def _read_required_document(files: SecureWorkspaceFiles, path: PurePosixPath) -> str:
    try:
        return files.read_text(path, max_bytes=_MAX_TASK_DOCUMENT_BYTES)
    except FileNotFoundError as exc:
        raise FileNotFoundError(
            f"feature task projection requires existing {path.as_posix()}"
        ) from exc


__all__ = ["project_feature_task", "project_feature_task_record"]
