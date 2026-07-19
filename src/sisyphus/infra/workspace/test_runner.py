from __future__ import annotations

from pathlib import Path
import os
import shlex
import subprocess
import sys

from .effects import TestExecution
from .errors import WorkspaceActionError


class SubprocessWorkspaceTests:
    def __init__(
        self,
        workspace: Path,
        *,
        commands: tuple[str, ...],
        timeout_seconds: float,
    ) -> None:
        self.workspace = workspace
        self.commands = commands
        self.timeout_seconds = timeout_seconds

    def run(self, command_id: int) -> TestExecution:
        if command_id < 0 or command_id >= len(self.commands):
            raise WorkspaceActionError(f"test command_id out of range: {command_id}")
        argv = shlex.split(self.commands[command_id])
        if not argv:
            raise WorkspaceActionError("configured test command is empty")
        if argv[0] in {"python", "python3"}:
            argv[0] = sys.executable
        try:
            completed = subprocess.run(
                argv,
                cwd=self.workspace,
                text=True,
                capture_output=True,
                timeout=self.timeout_seconds,
                env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
            )
        except subprocess.TimeoutExpired as exc:
            return TestExecution(
                ok=False,
                command_id=command_id,
                exit_code=None,
                error=f"test command timed out after {self.timeout_seconds:g} seconds",
                output=_timeout_output(exc),
            )
        except subprocess.SubprocessError as exc:
            return TestExecution(
                ok=False,
                command_id=command_id,
                exit_code=None,
                error=str(exc),
                output="",
            )
        output = (completed.stdout or "") + (completed.stderr or "")
        return TestExecution(
            ok=completed.returncode == 0,
            command_id=command_id,
            exit_code=completed.returncode,
            output=output,
            error=None if completed.returncode == 0 else f"test command exited with code {completed.returncode}",
        )


def _timeout_output(exc: subprocess.TimeoutExpired) -> str:
    stdout = exc.stdout.decode("utf-8", errors="replace") if isinstance(exc.stdout, bytes) else exc.stdout or ""
    stderr = exc.stderr.decode("utf-8", errors="replace") if isinstance(exc.stderr, bytes) else exc.stderr or ""
    return stdout + stderr


__all__ = ["SubprocessWorkspaceTests"]
