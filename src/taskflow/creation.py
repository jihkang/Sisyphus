from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import shutil

from .config import TaskflowConfig
from .gitops import GitOperationError, create_task_branch_and_worktree, remove_task_branch_and_worktree
from .state import build_task_record, load_task_record, save_task_record
from .templates import materialize_task_templates


class TaskCreationError(RuntimeError):
    """Raised when `taskflow new` cannot provision a task workspace."""


@dataclass(slots=True)
class CreateOutcome:
    task: dict
    task_file: Path


def create_task_workspace(
    repo_root: Path,
    config: TaskflowConfig,
    task_type: str,
    slug: str,
) -> CreateOutcome:
    task = build_task_record(
        repo_root=repo_root,
        config=config,
        task_type=task_type,
        slug=slug,
    )
    task_path = repo_root / task["task_dir"]
    task_file = task_path / "task.json"
    worktree = Path(task["worktree_path"])

    if task_path.exists():
        raise TaskCreationError(_existing_task_error(repo_root=repo_root, config=config, task=task, task_path=task_path))

    try:
        create_task_branch_and_worktree(
            repo_root=repo_root,
            branch=task["branch"],
            target_path=worktree,
            base_branch=task["base_branch"],
        )
    except GitOperationError as exc:
        raise TaskCreationError(str(exc)) from exc

    try:
        task_path.mkdir(parents=True, exist_ok=False)
        save_task_record(task_file=task_file, task=task)
        materialize_task_templates(task)
    except Exception as exc:
        rollback_errors = _rollback_created_task(repo_root=repo_root, task=task, task_path=task_path)
        if rollback_errors:
            details = "; ".join(rollback_errors)
            raise TaskCreationError(f"task creation failed and rollback was incomplete: {details}") from exc
        raise TaskCreationError(f"task creation failed: {exc}") from exc

    return CreateOutcome(task=task, task_file=task_file)


def _rollback_created_task(repo_root: Path, task: dict, task_path: Path) -> list[str]:
    errors: list[str] = []
    if task_path.exists():
        try:
            shutil.rmtree(task_path)
        except OSError as exc:
            errors.append(f"failed to remove task directory {task_path}: {exc}")

    try:
        remove_task_branch_and_worktree(
            repo_root=repo_root,
            branch=task["branch"],
            target_path=Path(task["worktree_path"]),
        )
    except GitOperationError as exc:
        errors.append(str(exc))

    return errors


def _existing_task_error(repo_root: Path, config: TaskflowConfig, task: dict, task_path: Path) -> str:
    try:
        existing, _ = load_task_record(repo_root, config.task_dir, task["id"])
    except (FileNotFoundError, OSError, ValueError):
        return f"task already exists: {task['id']} (task_dir: {task_path})"

    status = str(existing.get("status", "unknown"))
    branch = str(existing.get("branch", "unknown"))
    worktree_path = str(existing.get("worktree_path", "unknown"))
    if status == "closed":
        suggested_slug = _suggest_followup_slug(str(existing.get("slug") or task.get("slug") or "followup"))
        return (
            f"task already exists: {task['id']} "
            f"(status: {status}, branch: {branch}, task_dir: {task_path}, worktree_path: {worktree_path}); "
            f"create a follow-up task with a new slug such as `{suggested_slug}`"
        )
    return (
        f"task already exists: {task['id']} "
        f"(status: {status}, branch: {branch}, task_dir: {task_path}, worktree_path: {worktree_path}); "
        "use a new slug to create another task"
    )


def _suggest_followup_slug(slug: str) -> str:
    cleaned = slug.strip("-") or "followup"
    return f"{cleaned}-followup"
