"""Compatibility imports for the pre-migration workspace provider path."""

from __future__ import annotations

from ..infra.workspace import (
    MAX_READ_FILE_BYTES,
    PROTECTED_PATH_PARTS,
    SUPPORTED_ACTIONS,
    WorkspaceActionError,
    WorkspaceExecutor,
)

__all__ = [
    "PROTECTED_PATH_PARTS",
    "MAX_READ_FILE_BYTES",
    "SUPPORTED_ACTIONS",
    "WorkspaceActionError",
    "WorkspaceExecutor",
]
