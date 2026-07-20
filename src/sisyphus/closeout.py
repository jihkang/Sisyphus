from __future__ import annotations

from pathlib import Path

from .application.results.closeout import CloseOutcome
from .composition.closeout import build_closeout_service
from .infra.closeout import is_dirty_worktree, resolve_dirty_check_path
from .infra.config.loader import SisyphusConfig


def run_close(
    repo_root: Path,
    config: SisyphusConfig,
    task_id: str,
    allow_dirty: bool,
) -> CloseOutcome:
    return build_closeout_service(
        repo_root,
        config,
        dirty_checker=is_dirty_worktree,
    ).close(task_id, allow_dirty=allow_dirty)


_resolve_dirty_check_path = resolve_dirty_check_path


__all__ = ["CloseOutcome", "is_dirty_worktree", "run_close"]
