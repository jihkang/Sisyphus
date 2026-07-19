from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class PatchExecution:
    ok: bool
    error: str | None = None


@dataclass(frozen=True, slots=True)
class TestExecution:
    ok: bool
    command_id: int
    exit_code: int | None
    output: str
    error: str | None


class WorkspaceGitEffects(Protocol):
    def changed_files(self) -> tuple[str, ...]: ...

    def repository_files(self) -> tuple[str, ...]: ...

    def status(self) -> str: ...

    def diff_stat(self) -> str: ...

    def apply_patch(self, patch: str) -> PatchExecution: ...


class WorkspaceTestEffects(Protocol):
    def run(self, command_id: int) -> TestExecution: ...


__all__ = [
    "PatchExecution",
    "TestExecution",
    "WorkspaceGitEffects",
    "WorkspaceTestEffects",
]
