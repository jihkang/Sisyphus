from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from ..evolution.dataset import EvolutionDataset, project_evolution_dataset
from ..infra.clock import SystemClock
from ..infra.config.loader import SisyphusConfig, load_config
from ..infra.evolution import RepositoryEvolutionEvents, RepositoryEvolutionTaskQueries


def build_evolution_dataset(
    repo_root: Path,
    *,
    task_ids: Sequence[str] | None = None,
    max_events: int = 50,
    config: SisyphusConfig | None = None,
) -> EvolutionDataset:
    resolved_repo_root = repo_root.resolve()
    if not resolved_repo_root.exists():
        raise FileNotFoundError(f"repository root does not exist: {resolved_repo_root}")
    resolved_config = config or load_config(resolved_repo_root)
    return project_evolution_dataset(
        RepositoryEvolutionTaskQueries(resolved_repo_root, resolved_config),
        RepositoryEvolutionEvents(resolved_repo_root, resolved_config),
        SystemClock(),
        task_ids=task_ids,
        max_events=max_events,
    )


__all__ = ["build_evolution_dataset"]
