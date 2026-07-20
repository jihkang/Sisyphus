from __future__ import annotations

from collections.abc import Mapping
from dataclasses import replace
from pathlib import Path

from ...domain.agent.models import Agent
from ...domain.task.models import Task
from ...shared.paths import agent_dir, contained_path
from .agent_mapper import AGENT_RECORD_MAPPER
from .json_store import locked_json_update, read_json_file
from .record_mapper import RecordEnvelope
from .task_mapper import TASK_RECORD_MAPPER


class JsonTaskRepository:
    def __init__(self, repo_root: Path, task_dir_name: str) -> None:
        self._repo_root = repo_root
        self._task_dir_name = task_dir_name

    def get(self, task_id: str) -> Task:
        task_file = self._task_file(task_id)
        raw = read_json_file(task_file)
        if not isinstance(raw, Mapping):
            raise ValueError(f"task record must be a JSON object: {task_file}")
        return TASK_RECORD_MAPPER.decode(raw).model

    def save(self, task: Task) -> Task:
        if not task.task_id:
            raise ValueError("task_id is required to persist a task")
        task_file = self._task_file(task.task_id)

        def update(raw: object) -> dict:
            if not isinstance(raw, Mapping):
                raise ValueError(f"task record must be a JSON object: {task_file}")
            envelope = TASK_RECORD_MAPPER.decode(raw)
            updated = replace(envelope, model=task)
            return TASK_RECORD_MAPPER.encode(updated, include_defaults=True)

        locked_json_update(task_file, update, default_factory=dict)
        return task

    def _task_file(self, task_id: str) -> Path:
        tasks_root = contained_path(
            self._repo_root,
            self._task_dir_name,
            require_relative=True,
        )
        return contained_path(
            tasks_root,
            Path(task_id) / "task.json",
            require_relative=True,
        )


class JsonAgentRepository:
    def __init__(self, repo_root: Path, task_dir_name: str) -> None:
        self._repo_root = repo_root
        self._task_dir_name = task_dir_name

    def get(self, task_id: str, agent_id: str) -> Agent:
        agent_file = self._agent_file(task_id, agent_id)
        raw = read_json_file(agent_file)
        if not isinstance(raw, Mapping):
            raise ValueError(f"agent record must be a JSON object: {agent_file}")
        return AGENT_RECORD_MAPPER.decode(raw).model

    def save(self, agent: Agent) -> Agent:
        agent_file = self._agent_file(agent.parent_task_id, agent.agent_id)

        def update(raw: object) -> dict:
            if not isinstance(raw, Mapping):
                raise ValueError(f"agent record must be a JSON object: {agent_file}")
            if raw:
                envelope = replace(AGENT_RECORD_MAPPER.decode(raw), model=agent)
            else:
                envelope = AGENT_RECORD_MAPPER.envelope_for(agent)
            return AGENT_RECORD_MAPPER.encode(envelope, include_defaults=True)

        locked_json_update(agent_file, update, default_factory=dict)
        return agent

    def exists(self, task_id: str, agent_id: str) -> bool:
        return self._agent_file(task_id, agent_id).is_file()

    def list(self, *, task_id: str | None = None) -> tuple[Agent, ...]:
        if task_id is not None:
            paths = sorted(agent_dir(self._repo_root, self._task_dir_name, task_id).glob("*.json"))
        else:
            tasks_root = contained_path(
                self._repo_root,
                self._task_dir_name,
                require_relative=True,
            )
            paths = sorted(tasks_root.glob("*/agents/*.json")) if tasks_root.exists() else []
        agents: list[Agent] = []
        for path in paths:
            try:
                raw = read_json_file(path)
                if not isinstance(raw, Mapping):
                    continue
                agents.append(AGENT_RECORD_MAPPER.decode(raw).model)
            except (OSError, ValueError):
                continue
        return tuple(agents)

    def _agent_file(self, task_id: str, agent_id: str) -> Path:
        tasks_root = contained_path(
            self._repo_root,
            self._task_dir_name,
            require_relative=True,
        )
        agents_root = contained_path(
            tasks_root,
            Path(task_id) / "agents",
            require_relative=True,
        )
        return contained_path(
            agents_root,
            f"{agent_id}.json",
            require_relative=True,
        )


__all__ = ["JsonAgentRepository", "JsonTaskRepository"]
