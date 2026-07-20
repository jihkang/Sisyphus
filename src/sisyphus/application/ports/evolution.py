from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Protocol

from ..commands.evolution import RequestEvolutionFollowupCommand
from ..results.repository_requests import TaskRequestResult


class EvolutionTaskQueryPort(Protocol):
    @property
    def repo_root(self) -> Path: ...

    def list(self) -> tuple[dict[str, object], ...]: ...

    def load_with_path(self, task_id: str) -> tuple[dict[str, object], Path]: ...


class EvolutionEventPort(Protocol):
    @property
    def locator(self) -> Path: ...

    def read(self, *, limit: int) -> tuple[dict[str, object], ...]: ...

    def publish(
        self,
        *,
        event_type: str,
        source_module: str,
        data: Mapping[str, object] | None = None,
        source: Mapping[str, object] | None = None,
    ) -> None: ...


class EvolutionFollowupRequestPort(Protocol):
    def request(self, command: RequestEvolutionFollowupCommand) -> TaskRequestResult: ...


class EvolutionRunArtifactPort(Protocol):
    def create_run(self, run_id: str) -> Path: ...

    def artifact_dir(self, run_id: str) -> Path: ...

    def run_exists(self, run_id: str) -> bool: ...

    def artifact_exists(self, run_id: str, name: str) -> bool: ...

    def append_json(self, run_id: str, name: str, payload: Mapping[str, object]) -> Path: ...

    def append_text(self, run_id: str, name: str, content: str) -> Path: ...

    def read_json(self, run_id: str, name: str) -> Mapping[str, object] | None: ...

    def read_text(self, run_id: str, name: str) -> str | None: ...


__all__ = [
    "EvolutionEventPort",
    "EvolutionFollowupRequestPort",
    "EvolutionRunArtifactPort",
    "EvolutionTaskQueryPort",
]
