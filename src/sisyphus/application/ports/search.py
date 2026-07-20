from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Protocol

from ..search.models import SearchDocument, SearchIndexRebuildResult


class SearchIndexPort(Protocol):
    def rebuild(self) -> SearchIndexRebuildResult: ...

    def read(self) -> tuple[SearchDocument, ...]: ...

    def status(self) -> dict[str, object]: ...


class ContextPackStorePort(Protocol):
    def write(self, pack: Mapping[str, object]) -> Path: ...

    def read(self, pack_id: str) -> dict[str, object]: ...


__all__ = ["ContextPackStorePort", "SearchIndexPort"]
