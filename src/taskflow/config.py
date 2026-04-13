from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import tomllib


@dataclass(slots=True)
class EventBusConfig:
    provider: str = "noop"
    jsonl_path: str = ".planning/events.jsonl"


@dataclass(slots=True)
class TaskflowConfig:
    base_branch: str
    worktree_root: str
    task_dir: str
    branch_prefix_feature: str
    branch_prefix_issue: str
    commands: dict[str, str]
    verify: dict[str, list[str]]
    event_bus: EventBusConfig


def load_config(repo_root: Path) -> TaskflowConfig:
    config_path = repo_root / ".taskflow.toml"
    if not config_path.exists():
        return TaskflowConfig(
            base_branch="main",
            worktree_root="../_worktrees",
            task_dir=".planning/tasks",
            branch_prefix_feature="feat",
            branch_prefix_issue="fix",
            commands={},
            verify={"default": []},
            event_bus=EventBusConfig(),
        )

    raw = tomllib.loads(config_path.read_text(encoding="utf-8"))
    commands = raw.get("commands", {})
    verify = raw.get("verify", {})
    event_bus = _load_event_bus_config(raw.get("event_bus", {}))
    return TaskflowConfig(
        base_branch=raw.get("base_branch", "main"),
        worktree_root=raw.get("worktree_root", "../_worktrees"),
        task_dir=raw.get("task_dir", ".planning/tasks"),
        branch_prefix_feature=raw.get("branch_prefix_feature", "feat"),
        branch_prefix_issue=raw.get("branch_prefix_issue", "fix"),
        commands=dict(commands),
        verify={key: list(value) for key, value in dict(verify).items()},
        event_bus=event_bus,
    )


def _load_event_bus_config(raw: object) -> EventBusConfig:
    if not isinstance(raw, dict):
        return EventBusConfig()

    provider = str(raw.get("provider", "noop")).strip().lower() or "noop"
    jsonl_path = raw.get("jsonl_path", raw.get("path", ".planning/events.jsonl"))
    return EventBusConfig(
        provider=provider,
        jsonl_path=str(jsonl_path),
    )
