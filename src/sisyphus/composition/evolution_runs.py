from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from ..evolution.orchestrator import EvolutionExecutedRun, execute_evolution_run as execute_run
from ..infra.clock import SystemClock
from ..infra.config.loader import SisyphusConfig, load_config
from ..infra.evolution import RepositoryEvolutionEvents, RepositoryEvolutionRunStore
from .evolution_queries import build_evolution_dataset


def execute_evolution_run(
    repo_root: Path,
    *,
    target_ids: Sequence[str] | None = None,
    task_ids: Sequence[str] | None = None,
    max_events: int = 50,
    run_id: str | None = None,
    created_at: str | None = None,
    config: SisyphusConfig | None = None,
    **overrides: object,
) -> EvolutionExecutedRun:
    resolved_repo_root = repo_root.resolve()
    resolved_config = config or load_config(resolved_repo_root)
    dataset_builder = overrides.pop(
        "dataset_builder",
        lambda root, *, task_ids, max_events: build_evolution_dataset(
            root,
            task_ids=task_ids,
            max_events=max_events,
            config=resolved_config,
        ),
    )
    run_store = overrides.pop("run_store", RepositoryEvolutionRunStore(resolved_repo_root))
    events = overrides.pop("events", RepositoryEvolutionEvents(resolved_repo_root, resolved_config))
    clock = overrides.pop("clock", SystemClock())
    return execute_run(
        resolved_repo_root,
        target_ids=target_ids,
        task_ids=task_ids,
        max_events=max_events,
        run_id=run_id,
        created_at=created_at,
        dataset_builder=dataset_builder,
        run_store=run_store,
        events=events,
        clock=clock,
        **overrides,
    )


__all__ = ["execute_evolution_run"]
