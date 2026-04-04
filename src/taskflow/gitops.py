from __future__ import annotations

from pathlib import Path


def repo_name(repo_root: Path) -> str:
    return repo_root.name


def branch_name(task_type: str, slug: str, feature_prefix: str, issue_prefix: str) -> str:
    prefix = feature_prefix if task_type == "feature" else issue_prefix
    return f"{prefix}/{slug}"


def worktree_path(repo_root: Path, worktree_root: str, task_id: str) -> Path:
    root = (repo_root / worktree_root).resolve()
    return root / f"{repo_name(repo_root)}-{task_id}"
