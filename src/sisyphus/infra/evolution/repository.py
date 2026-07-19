from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from ...application.events import new_event_envelope
from ...shared.paths import task_dir as resolve_task_dir
from ..config.loader import SisyphusConfig
from ..events.publishers import (
    EventPublisher,
    build_event_publisher,
    read_jsonl_events,
    resolve_event_bus_path,
)
from ..persistence.task_records import FileTaskRecordAdapter


class RepositoryEvolutionTaskQueries:
    def __init__(self, repo_root: Path, config: SisyphusConfig) -> None:
        self._repo_root = repo_root.resolve()
        self._config = config
        self._records = FileTaskRecordAdapter(self._repo_root, config)

    @property
    def repo_root(self) -> Path:
        return self._repo_root

    def list(self) -> tuple[dict[str, object], ...]:
        return tuple(dict(task) for task in self._records.list())

    def load_with_path(self, task_id: str) -> tuple[dict[str, object], Path]:
        task = dict(self._records.load(task_id))
        task_file = resolve_task_dir(self._repo_root, self._config.task_dir, task_id) / "task.json"
        return task, task_file


class RepositoryEvolutionEvents:
    def __init__(
        self,
        repo_root: Path,
        config: SisyphusConfig,
        *,
        publisher: EventPublisher | None = None,
    ) -> None:
        self._repo_root = repo_root.resolve()
        self._config = config
        self._publisher = publisher or build_event_publisher(self._repo_root, config)

    @property
    def locator(self) -> Path:
        return resolve_event_bus_path(self._repo_root, self._config)

    def read(self, *, limit: int) -> tuple[dict[str, object], ...]:
        return tuple(read_jsonl_events(self.locator, limit=limit))

    def publish(
        self,
        *,
        event_type: str,
        source_module: str,
        data: Mapping[str, object] | None = None,
        source: Mapping[str, object] | None = None,
    ) -> None:
        payload_source = {"module": source_module}
        if source:
            payload_source.update(source)
        self._publisher.publish(
            new_event_envelope(
                event_type,
                source=payload_source,
                data=data or {},
            )
        )


__all__ = ["RepositoryEvolutionEvents", "RepositoryEvolutionTaskQueries"]
