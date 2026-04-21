from __future__ import annotations

from pathlib import Path
import subprocess


class GitOperationError(RuntimeError):
    """Raised when Sisyphus git workspace provisioning fails."""


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


def current_branch_name(repo_root: Path) -> str | None:
    completed = subprocess.run(
        ["git", "branch", "--show-current"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        return None
    branch = completed.stdout.strip()
    return branch or None


def list_dirty_paths(repo_root: Path) -> tuple[list[str], list[str]]:
    changed = _git_name_only(repo_root, ["diff", "--name-only", "HEAD", "--"])
    staged = _git_name_only(repo_root, ["diff", "--cached", "--name-only", "--"])
    untracked = _git_name_only(repo_root, ["ls-files", "--others", "--exclude-standard"])
    deleted = _git_name_only(repo_root, ["diff", "--name-only", "--diff-filter=D", "HEAD", "--"])
    staged_deleted = _git_name_only(repo_root, ["diff", "--cached", "--name-only", "--diff-filter=D", "--"])

    changed_paths = sorted({*changed, *staged, *untracked})
    deleted_paths = sorted({*deleted, *staged_deleted})
    return changed_paths, deleted_paths


def stage_all_changes(repo_root: Path) -> None:
    _run_git(
        repo_root,
        ["add", "-A"],
        error_prefix="failed to stage changes",
    )


def has_staged_changes(repo_root: Path) -> bool:
    completed = subprocess.run(
        ["git", "diff", "--cached", "--quiet", "--exit-code"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )
    return completed.returncode != 0


def current_head_sha(repo_root: Path) -> str:
    completed = _run_git(
        repo_root,
        ["rev-parse", "HEAD"],
        error_prefix="failed to resolve HEAD",
    )
    return completed.stdout.strip()


def commit_staged_changes(repo_root: Path, message: str) -> str:
    normalized_message = message.strip()
    if not normalized_message:
        raise GitOperationError("commit message must be non-empty")

    _run_git(
        repo_root,
        ["commit", "-m", normalized_message],
        error_prefix="failed to commit staged changes",
    )
    return current_head_sha(repo_root)


def push_branch(repo_root: Path, remote_name: str, branch: str, *, set_upstream: bool = True) -> None:
    normalized_remote = remote_name.strip()
    normalized_branch = branch.strip()
    if not normalized_remote:
        raise GitOperationError("remote name must be non-empty")
    if not normalized_branch:
        raise GitOperationError("branch name must be non-empty")

    args = ["push"]
    if set_upstream:
        args.append("-u")
    args.extend([normalized_remote, normalized_branch])
    _run_git(
        repo_root,
        args,
        error_prefix="failed to push branch",
    )


def remote_url(repo_root: Path, remote_name: str) -> str | None:
    normalized_remote = remote_name.strip()
    if not normalized_remote:
        return None
    completed = subprocess.run(
        ["git", "remote", "get-url", normalized_remote],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        return None
    value = completed.stdout.strip()
    return value or None


def copy_relative_path(source_root: Path, target_root: Path, relative_path: str) -> None:
    source_path = source_root / relative_path
    target_path = target_root / relative_path
    if source_path.is_dir():
        return
    target_path.parent.mkdir(parents=True, exist_ok=True)
    target_path.write_bytes(source_path.read_bytes())


def remove_relative_path(target_root: Path, relative_path: str) -> None:
    target_path = target_root / relative_path
    if not target_path.exists():
        return
    if target_path.is_dir():
        return
    target_path.unlink()


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


def _git_name_only(repo_root: Path, args: list[str]) -> list[str]:
    completed = subprocess.run(
        ["git", *args],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        return []
    return [line.strip() for line in completed.stdout.splitlines() if line.strip()]
