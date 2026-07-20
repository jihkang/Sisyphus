from __future__ import annotations

from collections.abc import Callable
from pathlib import Path, PurePosixPath

from ...domain.promotion.state import ensure_task_promotion_defaults
from ...domain.task.conformance import default_task_conformance, ensure_task_conformance_defaults
from ...domain.task.design import ensure_task_design_defaults
from ...domain.lifecycle import normalize_terminal_lifecycle_state
from ...domain.task.models import default_task_docs
from ...domain.task.strategy import sync_test_strategy_from_content
from ...shared.clock import utc_now
from ...shared.paths import PathBoundaryError, task_dir
from ..workspace.secure_files import SecureWorkspaceFiles
from .json_store import locked_json_update, read_json_file
from .task_mapper import TASK_RECORD_MAPPER


class ConcurrentTaskUpdateError(RuntimeError):
    """Raised when saving a task loaded before another writer updated it."""


_LOADED_TASK_MTIMES: dict[int, tuple[Path, int]] = {}
_MAX_TASK_SUPPORT_FILE_BYTES = 16 * 1024 * 1024


def load_task_record(repo_root: Path, task_dir_name: str, task_id: str) -> tuple[dict, Path]:
    task_file = task_dir(repo_root, task_dir_name, task_id) / "task.json"
    if not task_file.exists():
        raise FileNotFoundError(f"task not found: {task_id}")
    task = _map_task_record(read_json_file(task_file), task_file)
    task = normalize_task_projection(task, task_file=task_file)
    _remember_loaded_mtime(task, task_file)
    return task, task_file


def list_task_records(repo_root: Path, task_dir_name: str) -> list[dict]:
    root = repo_root / task_dir_name
    if not root.exists():
        return []

    tasks: list[dict] = []
    for task_file in sorted(root.glob("*/task.json")):
        try:
            task = _map_task_record(read_json_file(task_file), task_file)
            tasks.append(normalize_task_projection(task, task_file=task_file))
        except ValueError:
            continue
    return tasks


def save_task_record(
    task_file: Path,
    task: dict,
    *,
    sync_strategy: bool = True,
    mirror_support: bool = True,
) -> None:
    def replace(_: object) -> dict:
        _raise_if_stale_task(task_file, task)
        normalize_task_projection(task, task_file=task_file, sync_strategy=sync_strategy)
        task["updated_at"] = utc_now()
        return _map_task_record(task, task_file)

    locked_json_update(task_file, replace, default_factory=dict)
    _remember_loaded_mtime(task, task_file)
    if mirror_support:
        sync_task_support_files(task)


def update_task_record(
    repo_root: Path,
    task_dir_name: str,
    task_id: str,
    mutator: Callable[[dict], dict | None],
    *,
    sync_strategy: bool = True,
    mirror_support: bool = True,
) -> tuple[dict, Path]:
    task_file = task_dir(repo_root, task_dir_name, task_id) / "task.json"

    def update(raw: object) -> dict:
        if not isinstance(raw, dict):
            raise ValueError(f"task record must be a JSON object: {task_file}")
        task = normalize_task_projection(
            _map_task_record(raw, task_file),
            task_file=task_file,
            sync_strategy=sync_strategy,
        )
        replacement = mutator(task)
        if replacement is not None:
            task = replacement
        normalize_task_projection(task, task_file=task_file, sync_strategy=sync_strategy)
        task["updated_at"] = utc_now()
        return _map_task_record(task, task_file)

    task = locked_json_update(task_file, update)
    if not isinstance(task, dict):
        raise ValueError(f"task record must be a JSON object: {task_file}")
    _remember_loaded_mtime(task, task_file)
    if mirror_support:
        sync_task_support_files(task)
    return task, task_file


def ensure_task_record_defaults(task: dict) -> dict:
    task.setdefault("id", None)
    task.setdefault("type", None)
    task.setdefault("slug", None)
    task.setdefault("status", "open")
    task.setdefault("stage", "spec")
    task.setdefault("plan_status", "pending_review")
    task.setdefault("plan_reviewed_at", None)
    task.setdefault("plan_reviewed_by", None)
    task.setdefault("plan_review_notes", None)
    task.setdefault("plan_review_round", 0)
    task.setdefault("max_plan_review_rounds", 3)
    task.setdefault("plan_review_history", [])
    task.setdefault("workflow_phase", "plan_in_review")
    task.setdefault("spec_status", "draft")
    task.setdefault("spec_frozen_at", None)
    task.setdefault("spec_reviewed_by", None)
    task.setdefault("spec_review_notes", None)
    task.setdefault("audit_attempts", 0)
    task.setdefault("max_audit_attempts", 10)
    task.setdefault("created_at", utc_now())
    task.setdefault("updated_at", utc_now())
    task.setdefault("closed_at", None)
    task.setdefault("repo_root", "")
    task.setdefault("task_dir", "")
    task.setdefault("worktree_path", "")
    task.setdefault("branch", None)
    task.setdefault("base_branch", None)
    task.setdefault("verify_profile", "default")
    task.setdefault("verify_commands", [])
    task.setdefault("verify_status", "not_run")
    task.setdefault("last_verified_at", None)
    task.setdefault("last_verify_results", [])
    task.setdefault("test_strategy", {})
    task.setdefault("design", {})
    task.setdefault("promotion", {})
    task.setdefault("gates", [])
    task.setdefault("subtasks", [])
    if not isinstance(task.get("conformance"), dict):
        task["conformance"] = default_task_conformance()
    if not isinstance(task.get("docs"), dict):
        task["docs"] = {}
    for key, value in default_task_docs(task.get("type")).items():
        task["docs"].setdefault(key, value)
    if not isinstance(task.get("meta"), dict):
        task["meta"] = {"sequence": None, "close_override_used": False}
    else:
        task["meta"].setdefault("sequence", None)
        task["meta"].setdefault("close_override_used", False)
    ensure_task_design_defaults(task)
    ensure_task_promotion_defaults(task)
    ensure_task_conformance_defaults(task)
    return task


def normalize_task_projection(
    task: dict,
    *,
    task_file: Path | None = None,
    sync_strategy: bool = True,
) -> dict:
    ensure_task_record_defaults(task)
    normalize_terminal_lifecycle_state(task)
    if not sync_strategy:
        return task

    task_dir_path: Path | None = None
    if task_file is not None:
        task_dir_path = task_file.parent
    else:
        repo_root_value = str(task.get("repo_root", "")).strip()
        task_dir_value = str(task.get("task_dir", "")).strip()
        if repo_root_value and task_dir_value:
            repo_root = Path(repo_root_value)
            task_dir_path = repo_root / task_dir_value

    if task_dir_path is None or not task_dir_path.exists():
        return task
    source_name = "PLAN.md" if task["type"] == "feature" else "FIX_PLAN.md"
    source_path = task_dir_path / source_name
    if not source_path.exists():
        return task
    return sync_test_strategy_from_content(task, source_path.read_text(encoding="utf-8"))


def sync_task_support_files(task: dict) -> None:
    repo_root = Path(str(task.get("repo_root", "")))
    worktree_path = Path(str(task.get("worktree_path", "")))
    task_dir_value = str(task.get("task_dir") or "").strip()
    if not task_dir_value or not repo_root.is_dir() or not worktree_path.is_dir():
        return

    task_dir_relative = _support_relative_path(task_dir_value)
    source_task_dir = repo_root.joinpath(*task_dir_relative.parts)
    if not source_task_dir.is_dir():
        return

    source_files = SecureWorkspaceFiles(repo_root)
    target_files = SecureWorkspaceFiles(worktree_path)
    relative_paths = ["task.json", *[str(path) for path in task.get("docs", {}).values() if path]]
    for relative_path in relative_paths:
        support_path = task_dir_relative / _support_relative_path(relative_path)
        try:
            content = source_files.read_text(
                support_path,
                max_bytes=_MAX_TASK_SUPPORT_FILE_BYTES,
            )
        except FileNotFoundError:
            continue
        target_files.write_text_atomic(support_path, content)


def _support_relative_path(value: str) -> PurePosixPath:
    normalized = str(value).strip()
    if not normalized or normalized.startswith("/") or "\\" in normalized or "\x00" in normalized:
        raise PathBoundaryError(f"task support path must use relative POSIX syntax: {value}")
    parts = normalized.split("/")
    if any(part in {"", ".", ".."} for part in parts):
        raise PathBoundaryError(f"task support path contains unsafe traversal: {value}")
    return PurePosixPath(*parts)


def _remember_loaded_mtime(task: dict, task_file: Path) -> None:
    try:
        _LOADED_TASK_MTIMES[id(task)] = (task_file.resolve(), task_file.stat().st_mtime_ns)
    except FileNotFoundError:
        _LOADED_TASK_MTIMES.pop(id(task), None)


def _raise_if_stale_task(task_file: Path, task: dict) -> None:
    loaded = _LOADED_TASK_MTIMES.get(id(task))
    if loaded is None or not task_file.exists():
        return
    loaded_path, loaded_mtime = loaded
    if loaded_path != task_file.resolve():
        return
    current_mtime = task_file.stat().st_mtime_ns
    if current_mtime != loaded_mtime:
        raise ConcurrentTaskUpdateError(f"task record changed before save: {task_file}")


def _map_task_record(raw: object, task_file: Path) -> dict:
    if not isinstance(raw, dict):
        raise ValueError(f"task record must be a JSON object: {task_file}")
    return TASK_RECORD_MAPPER.encode(TASK_RECORD_MAPPER.decode(raw))


__all__ = [
    "ConcurrentTaskUpdateError",
    "ensure_task_record_defaults",
    "list_task_records",
    "load_task_record",
    "normalize_task_projection",
    "save_task_record",
    "sync_task_support_files",
    "update_task_record",
]
