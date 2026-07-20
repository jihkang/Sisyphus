from __future__ import annotations

from pathlib import Path

from ..application.metrics import build_value_metrics_report as project_value_metrics_report
from ..infra.clock import SystemClock
from ..infra.config.loader import SisyphusConfig
from ..infra.metrics import metric_event_paths, read_metric_entries
from ..infra.persistence.task_repository import list_task_records


def build_value_metrics_report(
    repo_root: Path,
    config: SisyphusConfig,
) -> dict[str, object]:
    tasks = list_task_records(repo_root=repo_root, task_dir_name=config.task_dir)
    paths = metric_event_paths(repo_root, config)
    return project_value_metrics_report(
        tasks=tasks,
        entries=read_metric_entries(paths),
        event_log_paths=[str(path) for path in paths],
        generated_at=SystemClock().now(),
    )


__all__ = ["build_value_metrics_report"]
