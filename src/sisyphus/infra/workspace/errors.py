from __future__ import annotations


class WorkspaceActionError(ValueError):
    pass


class WorkspaceFileSafetyError(ValueError):
    pass


class WorkspaceGitError(RuntimeError):
    pass


__all__ = ["WorkspaceActionError", "WorkspaceFileSafetyError", "WorkspaceGitError"]
