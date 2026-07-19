from __future__ import annotations

from pathlib import Path
import subprocess

from .effects import PatchExecution
from .errors import WorkspaceGitError


class SubprocessWorkspaceGit:
    def __init__(self, workspace: Path, *, timeout_seconds: float) -> None:
        self.workspace = workspace
        self.timeout_seconds = timeout_seconds

    def changed_files(self) -> tuple[str, ...]:
        tracked = self._run_checked(
            ["diff", "--name-only", "--diff-filter=ACMRTUXB", "HEAD"]
        )
        untracked = self._run_checked(["ls-files", "--others", "--exclude-standard"])
        return _nonempty_lines(tracked, untracked)

    def repository_files(self) -> tuple[str, ...]:
        output = self._run_checked(["ls-files", "--cached", "--others", "--exclude-standard"])
        return _nonempty_lines(output)

    def status(self) -> str:
        return self._run_checked(["status", "--short"])

    def diff_stat(self) -> str:
        return self._run_checked(["diff", "--stat", "HEAD"])

    def apply_patch(self, patch: str) -> PatchExecution:
        try:
            checked = self._run(["apply", "--check", "-"], input_text=patch)
        except WorkspaceGitError as exc:
            return PatchExecution(ok=False, error=str(exc))
        if checked.returncode != 0:
            return PatchExecution(
                ok=False,
                error=checked.stderr or checked.stdout or "git apply --check failed",
            )
        try:
            applied = self._run(
                ["apply", "--whitespace=nowarn", "-"],
                input_text=patch,
            )
        except WorkspaceGitError as exc:
            return PatchExecution(ok=False, error=str(exc))
        if applied.returncode != 0:
            return PatchExecution(
                ok=False,
                error=applied.stderr or applied.stdout or "git apply failed",
            )
        return PatchExecution(ok=True)

    def _run_checked(self, args: list[str]) -> str:
        completed = self._run(args)
        if completed.returncode != 0:
            raise WorkspaceGitError(
                completed.stderr or completed.stdout or f"git {' '.join(args)} failed"
            )
        return completed.stdout

    def _run(
        self,
        args: list[str],
        *,
        input_text: str | None = None,
    ) -> subprocess.CompletedProcess[str]:
        try:
            return subprocess.run(
                ["git", *args],
                cwd=self.workspace,
                input=input_text,
                text=True,
                capture_output=True,
                timeout=self.timeout_seconds,
            )
        except subprocess.TimeoutExpired as exc:
            raise WorkspaceGitError(f"git command timed out: {' '.join(args)}") from exc
        except subprocess.SubprocessError as exc:
            raise WorkspaceGitError(f"git command failed: {' '.join(args)}: {exc}") from exc


def _nonempty_lines(*outputs: str) -> tuple[str, ...]:
    return tuple(
        line.strip()
        for output in outputs
        for line in output.splitlines()
        if line.strip()
    )


__all__ = ["SubprocessWorkspaceGit"]
