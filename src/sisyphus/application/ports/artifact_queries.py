from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


@dataclass(frozen=True, slots=True)
class FeatureArtifactReadModel:
    task_id: str
    feature_id: str
    artifact_graph: Mapping[str, object]
    slot_bindings: Mapping[str, object]
    verification_claims: tuple[Mapping[str, object], ...]
    promotion: Mapping[str, object]
    invalidation: Mapping[str, object]
    derived_state: str
    compiled_obligations: Mapping[str, object] | None = None


class FeatureArtifactQueryPort(Protocol):
    def read_snapshot(
        self,
        task: Mapping[str, object],
        task_dir: Path,
    ) -> Mapping[str, object] | None: ...

    def project_current(
        self,
        task: Mapping[str, object],
        task_dir: Path,
        *,
        include_compiled_obligations: bool,
    ) -> FeatureArtifactReadModel: ...

    def read_compiled_obligations(
        self,
        task_dir: Path,
    ) -> Mapping[str, object] | None: ...


__all__ = ["FeatureArtifactQueryPort", "FeatureArtifactReadModel"]
