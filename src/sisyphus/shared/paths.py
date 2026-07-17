from __future__ import annotations

from pathlib import Path


class PathBoundaryError(ValueError):
    """Raised when a path crosses a configured filesystem boundary."""


def contained_path(
    root: Path,
    path: str | Path,
    *,
    require_relative: bool = False,
) -> Path:
    root_path = Path(root)
    requested_path = Path(path)
    if require_relative and requested_path.is_absolute():
        raise PathBoundaryError(f"path must be relative to root: {path}")

    candidate = requested_path if requested_path.is_absolute() else root_path / requested_path
    resolved_root = root_path.resolve()
    resolved_candidate = candidate.resolve(strict=False)
    try:
        resolved_candidate.relative_to(resolved_root)
    except ValueError as exc:
        raise PathBoundaryError(f"path escapes root {resolved_root}: {path}") from exc
    if require_relative and resolved_candidate == resolved_root:
        raise PathBoundaryError(f"path must identify a child of root: {path}")
    return candidate


def planning_dir(repo_root: Path) -> Path:
    return repo_root / ".planning"


def task_dir(repo_root: Path, task_dir_name: str, task_id: str) -> Path:
    return repo_root / task_dir_name / task_id


def agent_dir(repo_root: Path, task_dir_name: str, task_id: str) -> Path:
    return task_dir(repo_root, task_dir_name, task_id) / "agents"


def inbox_dir(repo_root: Path) -> Path:
    return planning_dir(repo_root) / "inbox"


def inbox_pending_dir(repo_root: Path) -> Path:
    return inbox_dir(repo_root) / "pending"


def inbox_processing_dir(repo_root: Path) -> Path:
    return inbox_dir(repo_root) / "processing"


def inbox_processed_dir(repo_root: Path) -> Path:
    return inbox_dir(repo_root) / "processed"


def inbox_failed_dir(repo_root: Path) -> Path:
    return inbox_dir(repo_root) / "failed"


def event_log_file(repo_root: Path) -> Path:
    return planning_dir(repo_root) / "events.jsonl"


def workflow_candidate_index_file(repo_root: Path) -> Path:
    return planning_dir(repo_root) / "cache" / "workflow-candidates.json"
