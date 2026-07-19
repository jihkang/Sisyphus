from __future__ import annotations

from collections.abc import Mapping
from typing import Protocol

from ..results.artifacts import ArtifactRef


class ArtifactStorePort(Protocol):
    def write_json(
        self,
        task_id: str,
        relative_path: str,
        payload: Mapping[str, object],
    ) -> ArtifactRef: ...

    def write_text(self, task_id: str, relative_path: str, content: str) -> ArtifactRef: ...


__all__ = ["ArtifactStorePort"]
