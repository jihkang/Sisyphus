from __future__ import annotations

from pathlib import Path

from .application.commands.task import CreateTaskRecordCommand
from .application.results.task_creation import CreateOutcome
from .application.use_cases.task_creation import TaskCreationError
from .composition.task_creation import build_task_workspace_creation_service
from .infra.config.loader import SisyphusConfig
from .templates import materialize_task_templates


def create_task_workspace(
    repo_root: Path,
    config: SisyphusConfig,
    task_type: str,
    slug: str,
) -> CreateOutcome:
    return build_task_workspace_creation_service(
        repo_root,
        config,
        template_materializer=materialize_task_templates,
    ).create(
        CreateTaskRecordCommand(
            task_type=task_type,
            slug=slug,
            spec_validation_required=True,
        )
    )


__all__ = ["CreateOutcome", "TaskCreationError", "create_task_workspace"]
