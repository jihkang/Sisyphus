from __future__ import annotations

import json
from pathlib import Path
import re
import subprocess
from typing import Protocol

from ...application.ports.promotion import PullRequestSpec
from ...gitops import (
    GitOperationError,
    commit_staged_changes,
    has_staged_changes,
    push_branch,
    push_revision,
    remote_url,
    stage_all_changes,
)


class GhRunner(Protocol):
    def __call__(
        self,
        repo_root: Path,
        args: list[str],
        *,
        error_prefix: str,
    ) -> subprocess.CompletedProcess[str]: ...


class GitVersionControlAdapter:
    def workspace_exists(self, workspace: str) -> bool:
        return Path(workspace).is_dir()

    def stage_all(self, workspace: str) -> None:
        stage_all_changes(Path(workspace))

    def has_staged_changes(self, workspace: str) -> bool:
        return has_staged_changes(Path(workspace))

    def commit(self, workspace: str, message: str) -> str:
        return commit_staged_changes(Path(workspace), message)

    def push(self, workspace: str, remote: str, branch: str) -> None:
        push_branch(Path(workspace), remote, branch, set_upstream=True)

    def push_revision(
        self,
        workspace: str,
        remote: str,
        revision: str,
        branch: str,
    ) -> None:
        push_revision(Path(workspace), remote, revision, branch)

    def remote_url(self, workspace: str, remote: str) -> str | None:
        return remote_url(Path(workspace), remote)


class GithubCliPullRequestAdapter:
    def __init__(self, runner: GhRunner) -> None:
        self._runner = runner

    def find_open(self, spec: PullRequestSpec) -> str | None:
        args = [
            "pr",
            "list",
            "--state",
            "open",
            "--base",
            spec.base_branch,
            "--head",
            spec.head_branch,
            "--json",
            "url",
            "--limit",
            "1",
        ]
        if spec.repo_full_name:
            args.extend(["--repo", spec.repo_full_name])
        completed = self._runner(
            Path(spec.workspace),
            args,
            error_prefix="failed to find existing pull request",
        )
        output = (completed.stdout or "").strip()
        if not output:
            return None
        try:
            payload = json.loads(output)
        except json.JSONDecodeError:
            pull_request_url = _extract_pull_request_url(output)
            if pull_request_url is not None:
                return pull_request_url
            raise GitOperationError(
                "failed to find existing pull request: gh returned invalid JSON"
            )
        if not isinstance(payload, list):
            raise GitOperationError(
                "failed to find existing pull request: gh returned a non-array response"
            )
        if not payload:
            return None
        first = payload[0]
        if not isinstance(first, dict):
            raise GitOperationError(
                "failed to find existing pull request: gh returned an invalid entry"
            )
        pull_request_url = _extract_pull_request_url(str(first.get("url") or ""))
        if pull_request_url is None:
            raise GitOperationError(
                "failed to find existing pull request: gh omitted the pull request URL"
            )
        return pull_request_url

    def create(self, spec: PullRequestSpec) -> str:
        args = [
            "pr",
            "create",
            "--base",
            spec.base_branch,
            "--head",
            spec.head_branch,
            "--title",
            spec.title,
            "--body",
            spec.body,
        ]
        if spec.draft:
            args.append("--draft")
        if spec.repo_full_name:
            args.extend(["--repo", spec.repo_full_name])
        completed = self._runner(
            Path(spec.workspace),
            args,
            error_prefix="failed to create pull request",
        )
        pull_request_url = _extract_pull_request_url(completed.stdout)
        if pull_request_url is None:
            pull_request_url = _extract_pull_request_url(completed.stderr)
        if pull_request_url is None:
            raise GitOperationError(
                "failed to create pull request: gh did not return a pull request URL"
            )
        return pull_request_url


def run_gh(
    repo_root: Path,
    args: list[str],
    *,
    error_prefix: str,
) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(
        ["gh", *args],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode == 0:
        return completed
    message = (completed.stderr or completed.stdout or "").strip() or "gh command failed"
    raise GitOperationError(f"{error_prefix}: {message}")


def _extract_pull_request_url(output: str | None) -> str | None:
    if not output:
        return None
    match = re.search(r"https://github\.com/\S+/pull/\d+", output)
    return match.group(0) if match else None


__all__ = [
    "GhRunner",
    "GitVersionControlAdapter",
    "GithubCliPullRequestAdapter",
    "run_gh",
]
