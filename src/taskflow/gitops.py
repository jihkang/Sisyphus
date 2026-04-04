from __future__ import annotations

from pathlib import Path
import subprocess


class GitOperationError(RuntimeError):
    """Raised when taskflow git workspace provisioning fails."""


def repo_name(repo_root: Path) -> str:
    return repo_root.name


def branch_name(task_type: str, slug: str, feature_prefix: str, issue_prefix: str) -> str:
    prefix = feature_prefix if task_type == "feature" else issue_prefix
    return f"{prefix}/{slug}"


def worktree_path(repo_root: Path, worktree_root: str, task_id: str) -> Path:
    root = (repo_root / worktree_root).resolve()
    return root / f"{repo_name(repo_root)}-{task_id}"


def create_task_branch_and_worktree(repo_root: Path, branch: str, target_path: Path, base_branch: str) -> None:
    if local_branch_exists(repo_root, branch):
        raise GitOperationError(f"branch already exists: {branch}")
    if target_path.exists():
        raise GitOperationError(f"worktree path already exists: {target_path}")

    base_ref = resolve_base_ref(repo_root, base_branch)
    if not base_ref:
        raise GitOperationError(f"base branch not found: {base_branch}")

    target_path.parent.mkdir(parents=True, exist_ok=True)
    _run_git(
        repo_root,
        ["worktree", "add", "-b", branch, str(target_path), base_ref],
        error_prefix="failed to create branch/worktree",
    )


def remove_task_branch_and_worktree(repo_root: Path, branch: str, target_path: Path) -> None:
    if target_path.exists():
        _run_git(
            repo_root,
            ["worktree", "remove", "--force", str(target_path)],
            error_prefix="failed to remove worktree during rollback",
        )
    if local_branch_exists(repo_root, branch):
        _run_git(
            repo_root,
            ["branch", "-D", branch],
            error_prefix="failed to delete branch during rollback",
        )


def local_branch_exists(repo_root: Path, branch: str) -> bool:
    result = subprocess.run(
        ["git", "show-ref", "--verify", "--quiet", f"refs/heads/{branch}"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )
    return result.returncode == 0


def resolve_base_ref(repo_root: Path, base_branch: str) -> str | None:
    candidates = [
        base_branch,
        f"refs/heads/{base_branch}",
        f"origin/{base_branch}",
        f"refs/remotes/origin/{base_branch}",
    ]
    for candidate in candidates:
        if _git_ref_exists(repo_root, candidate):
            return candidate
    return None


def _git_ref_exists(repo_root: Path, ref: str) -> bool:
    result = subprocess.run(
        ["git", "rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )
    return result.returncode == 0


def _run_git(repo_root: Path, args: list[str], error_prefix: str) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(
        ["git", *args],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode == 0:
        return completed

    message = (completed.stderr or completed.stdout or "").strip()
    if not message:
        message = "git command failed"
    raise GitOperationError(f"{error_prefix}: {message}")
