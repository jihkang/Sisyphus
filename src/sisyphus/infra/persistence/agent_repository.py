from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from ...shared.paths import agent_dir
from .agent_mapper import AGENT_RECORD_MAPPER
from .json_store import locked_json_update, read_json_file


class ConcurrentAgentUpdateError(RuntimeError):
    """Raised when saving an agent loaded before another writer updated it."""


_LOADED_AGENT_MTIMES: dict[int, tuple[Path, int]] = {}


def agent_file(repo_root: Path, task_dir_name: str, task_id: str, agent_id: str) -> Path:
    return agent_dir(repo_root, task_dir_name, task_id) / f"{agent_id}.json"


def list_agent_files(repo_root: Path, task_dir_name: str, *, task_id: str | None = None) -> list[Path]:
    if task_id:
        root = agent_dir(repo_root, task_dir_name, task_id)
        if root.exists():
            return sorted(root.glob("*.json"))
        return []

    root = repo_root / task_dir_name
    if root.exists():
        return sorted(root.glob("*/agents/*.json"))
    return []


def read_agent_record(agent_file: Path) -> dict:
    agent = _map_agent_record(read_json_file(agent_file), agent_file)
    _remember_loaded_mtime(agent, agent_file)
    return agent


def save_agent_record(agent_file: Path, agent: dict) -> None:
    def replace(_: object) -> dict:
        _raise_if_stale_agent(agent_file, agent)
        return _map_agent_record(agent, agent_file)

    locked_json_update(agent_file, replace, default_factory=dict)
    _remember_loaded_mtime(agent, agent_file)


def update_agent_record(agent_file: Path, mutator: Callable[[dict], dict | None]) -> dict:
    def update(raw: object) -> dict:
        if not isinstance(raw, dict):
            raise ValueError(f"agent record must be a JSON object: {agent_file}")
        raw = _map_agent_record(raw, agent_file)
        replacement = mutator(raw)
        if replacement is not None:
            raw = replacement
        if not isinstance(raw, dict):
            raise ValueError(f"agent record must be a JSON object: {agent_file}")
        return _map_agent_record(raw, agent_file)

    agent = locked_json_update(agent_file, update)
    if not isinstance(agent, dict):
        raise ValueError(f"agent record must be a JSON object: {agent_file}")
    _remember_loaded_mtime(agent, agent_file)
    return agent


def _remember_loaded_mtime(agent: dict, agent_file: Path) -> None:
    try:
        _LOADED_AGENT_MTIMES[id(agent)] = (agent_file.resolve(), agent_file.stat().st_mtime_ns)
    except FileNotFoundError:
        _LOADED_AGENT_MTIMES.pop(id(agent), None)


def _raise_if_stale_agent(agent_file: Path, agent: dict) -> None:
    loaded = _LOADED_AGENT_MTIMES.get(id(agent))
    if loaded is None or not agent_file.exists():
        return
    loaded_path, loaded_mtime = loaded
    if loaded_path != agent_file.resolve():
        return
    current_mtime = agent_file.stat().st_mtime_ns
    if current_mtime != loaded_mtime:
        raise ConcurrentAgentUpdateError(f"agent record changed before save: {agent_file}")


def _map_agent_record(raw: object, agent_file: Path) -> dict:
    if not isinstance(raw, dict):
        raise ValueError(f"agent record must be a JSON object: {agent_file}")
    return AGENT_RECORD_MAPPER.encode(AGENT_RECORD_MAPPER.decode(raw))


__all__ = [
    "ConcurrentAgentUpdateError",
    "agent_file",
    "list_agent_files",
    "read_agent_record",
    "save_agent_record",
    "update_agent_record",
]
