from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
import subprocess

from ...application.ports.workflow import TaskRecord


DirtyChecker = Callable[[Path], bool]


def is_dirty_worktree(path: Path) -> bool:
    try:
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=path,
            check=True,
            capture_output=True,
            text=True,
        )
        return bool(result.stdout.strip())
    except (subprocess.CalledProcessError, FileNotFoundError, NotADirectoryError, OSError):
        return False


def resolve_dirty_check_path(repo_root: Path, task: TaskRecord) -> Path:
    candidates = [task.get("worktree_path"), task.get("repo_root"), str(repo_root)]
    for candidate in candidates:
        if not candidate:
            continue
        resolved = Path(str(candidate))
        if resolved.is_dir():
            return resolved
    return repo_root


class GitWorktreeStatusAdapter:
    def __init__(self, repo_root: Path, dirty_checker: DirtyChecker = is_dirty_worktree) -> None:
        self._repo_root = repo_root
        self._dirty_checker = dirty_checker

    def is_dirty(self, task: TaskRecord) -> bool:
        return self._dirty_checker(resolve_dirty_check_path(self._repo_root, task))


__all__ = [
    "DirtyChecker",
    "GitWorktreeStatusAdapter",
    "is_dirty_worktree",
    "resolve_dirty_check_path",
]
