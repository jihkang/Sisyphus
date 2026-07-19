from __future__ import annotations

from pathlib import Path

from ...application.use_cases.workflow import PLANNER_ROLE, REVIEWER_ROLE, WORKER_ROLE
from ...composition.workflow import build_workflow_service
from ...config import SisyphusConfig
from ..persistence.workflow_candidates import list_workflow_candidate_ids
from ..providers import run_legacy_provider_wrapper as run_provider_wrapper


def run_workflow_cycle(repo_root: Path, config: SisyphusConfig) -> int:
    progressed = 0
    task_ids = list_workflow_candidate_ids(
        repo_root=repo_root,
        task_dir_name=config.task_dir,
    )
    for task_id in task_ids:
        if _advance_task(repo_root=repo_root, config=config, task_id=task_id):
            progressed += 1
    return progressed


def _advance_task(repo_root: Path, config: SisyphusConfig, task_id: str) -> bool:
    service = build_workflow_service(
        repo_root,
        config,
        provider_runner=run_provider_wrapper,
    )
    return service.advance(task_id)


__all__ = [
    "PLANNER_ROLE",
    "REVIEWER_ROLE",
    "WORKER_ROLE",
    "run_workflow_cycle",
]
