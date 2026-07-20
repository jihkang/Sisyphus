from __future__ import annotations

from collections.abc import Mapping
from typing import Protocol


SUPPORTED_WORKSPACE_ACTIONS = (
    "apply_patch",
    "git_diff",
    "list_files",
    "read_file",
    "run_test",
    "search",
    "write_file",
)


class WorkspacePort(Protocol):
    blocked_action_count: int

    def execute(self, action: Mapping[str, object], *, step: int) -> dict[str, object]: ...

    def completion_facts(self) -> dict[str, object]: ...


__all__ = ["SUPPORTED_WORKSPACE_ACTIONS", "WorkspacePort"]
