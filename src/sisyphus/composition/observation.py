from __future__ import annotations

from pathlib import Path

from ..application.observation import OBSERVATION_SCHEMA_VERSION, project_task_observation
from ..infra.config.loader import SisyphusConfig
from ..infra.observation import required_document_status
from .action_space import allowed_policy_actions, forbidden_policy_actions
from .evidence import summarize_evidence_graph
from .repository_requests import load_task_record_with_path


def build_task_observation(task: dict, task_dir: Path) -> dict[str, object]:
    return project_task_observation(
        task,
        required_docs=required_document_status(task, task_dir),
        evidence_summary=summarize_evidence_graph(task, task_dir),
        allowed_next_actions=allowed_policy_actions(task),
        forbidden_next_actions=forbidden_policy_actions(task),
    )


def render_task_observation(
    repo_root: Path,
    config: SisyphusConfig,
    task_id: str,
) -> dict[str, object]:
    task, task_file = load_task_record_with_path(
        repo_root=repo_root,
        config=config,
        task_id=task_id,
    )
    return build_task_observation(task, task_file.parent)


__all__ = [
    "OBSERVATION_SCHEMA_VERSION",
    "build_task_observation",
    "render_task_observation",
]
