from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from ..infra.config.loader import SisyphusConfig, load_config
from ..infra.evolution import RepositoryEvolutionEvents


def publish_evolution_event(
    repo_root: Path,
    *,
    config: SisyphusConfig | None = None,
    event_type: str,
    source_module: str,
    data: Mapping[str, object] | None = None,
    source: Mapping[str, object] | None = None,
) -> None:
    resolved_root = repo_root.resolve()
    resolved_config = config or load_config(resolved_root)
    RepositoryEvolutionEvents(resolved_root, resolved_config).publish(
        event_type=event_type,
        source_module=source_module,
        data=data,
        source=source,
    )


__all__ = ["publish_evolution_event"]
