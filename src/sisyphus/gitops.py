from __future__ import annotations

from pathlib import Path
import os
import re
import subprocess

from .shared.paths import contained_path


class GitOperationError(RuntimeError):
    """Raised when Sisyphus git workspace provisioning fails."""


_GIT_OBJECT_ID = re.compile(r"^[0-9a-fA-F]{40,64}$")
_REMOTE_QUERY_TIMEOUT_SECONDS = 30.0


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
    try:
        completed = subprocess.run(
            [
                "git",
                "status",
                "--porcelain=v1",
                "-z",
                "--untracked-files=all",
                "--ignored=no",
            ],
            cwd=repo_root,
            capture_output=True,
            text=False,
            check=False,
        )
    except OSError as exc:
        raise GitOperationError(f"failed to inspect dirty paths: {exc}") from exc
    if completed.returncode != 0:
        detail = os.fsdecode(completed.stderr or completed.stdout).strip()
        raise GitOperationError(
            "failed to inspect dirty paths: " + (detail or "git status failed")
        )
    return _parse_porcelain_v1_z(completed.stdout)


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


def revision_sha(repo_root: Path, revision: str) -> str:
    normalized_revision = revision.strip()
    if not normalized_revision:
        raise GitOperationError("revision must be non-empty")
    completed = _run_git(
        repo_root,
        ["rev-parse", "--verify", f"{normalized_revision}^{{commit}}"],
        error_prefix=f"failed to resolve revision `{normalized_revision}`",
    )
    return completed.stdout.strip()


def remote_branch_sha(repo_root: Path, remote_name: str, branch: str) -> str:
    normalized_remote = remote_name.strip()
    normalized_branch = branch.strip()
    if not normalized_remote:
        raise GitOperationError("remote name must be non-empty")
    if not normalized_branch:
        raise GitOperationError("branch name must be non-empty")
    expected_ref = f"refs/heads/{normalized_branch}"
    env = dict(os.environ)
    env["GIT_TERMINAL_PROMPT"] = "0"
    try:
        completed = subprocess.run(
            [
                "git",
                "ls-remote",
                "--exit-code",
                "--heads",
                "--",
                normalized_remote,
                expected_ref,
            ],
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=False,
            timeout=_REMOTE_QUERY_TIMEOUT_SECONDS,
            env=env,
        )
    except subprocess.TimeoutExpired as exc:
        raise GitOperationError(
            f"failed to resolve remote branch `{normalized_remote}/{normalized_branch}`: timed out"
        ) from exc
    except OSError as exc:
        raise GitOperationError(
            f"failed to resolve remote branch `{normalized_remote}/{normalized_branch}`: {exc}"
        ) from exc
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "").strip() or "git ls-remote failed"
        raise GitOperationError(
            f"failed to resolve remote branch `{normalized_remote}/{normalized_branch}`: {detail}"
        )
    matches: list[str] = []
    for line in completed.stdout.splitlines():
        fields = line.split("\t", 1)
        if len(fields) != 2 or fields[1] != expected_ref:
            continue
        object_id = fields[0].strip()
        if not _GIT_OBJECT_ID.fullmatch(object_id):
            raise GitOperationError("git ls-remote returned an invalid object ID")
        matches.append(object_id.lower())
    if len(matches) != 1:
        raise GitOperationError(
            f"remote branch `{normalized_remote}/{normalized_branch}` did not resolve uniquely"
        )
    return matches[0]


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


def push_revision(
    repo_root: Path,
    remote_name: str,
    revision: str,
    branch: str,
) -> None:
    normalized_remote = remote_name.strip()
    normalized_revision = revision.strip()
    normalized_branch = branch.strip()
    if not normalized_remote:
        raise GitOperationError("remote name must be non-empty")
    if not normalized_revision:
        raise GitOperationError("revision must be non-empty")
    if not normalized_branch:
        raise GitOperationError("branch name must be non-empty")
    _run_git(
        repo_root,
        [
            "push",
            normalized_remote,
            f"{normalized_revision}:refs/heads/{normalized_branch}",
        ],
        error_prefix="failed to push reviewed revision",
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
    source_path = contained_path(source_root, relative_path, require_relative=True)
    target_path = contained_path(target_root, relative_path, require_relative=True)
    if source_path.is_dir():
        return
    target_path.parent.mkdir(parents=True, exist_ok=True)
    target_path.write_bytes(source_path.read_bytes())


def remove_relative_path(target_root: Path, relative_path: str) -> None:
    target_path = contained_path(target_root, relative_path, require_relative=True)
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


def _parse_porcelain_v1_z(payload: bytes) -> tuple[list[str], list[str]]:
    records = payload.split(b"\0")
    changed: set[str] = set()
    deleted: set[str] = set()
    index = 0
    while index < len(records):
        record = records[index]
        index += 1
        if not record:
            continue
        if len(record) < 4 or record[2:3] != b" ":
            raise GitOperationError("failed to parse NUL-delimited git status output")
        try:
            status = record[:2].decode("ascii")
        except UnicodeDecodeError as exc:
            raise GitOperationError("git status returned a non-ASCII status code") from exc
        path = os.fsdecode(record[3:])
        if not path:
            raise GitOperationError("git status returned an empty path")
        changed.add(path)
        if "D" in status:
            deleted.add(path)

        if "R" in status or "C" in status:
            if index >= len(records) or not records[index]:
                raise GitOperationError("git status omitted a rename or copy source path")
            source_path = os.fsdecode(records[index])
            index += 1
            changed.add(source_path)
            if "R" in status:
                deleted.add(source_path)
    return sorted(changed), sorted(deleted)
