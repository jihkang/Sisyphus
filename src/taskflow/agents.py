from __future__ import annotations

from datetime import datetime, timezone
from functools import wraps
from pathlib import Path
import json

from .config import TaskflowConfig
from .paths import agent_dir
from .state import load_task_record, utc_now
from .utils import find_unknown_fields


DEFAULT_STALE_AFTER_SECONDS = 900
ACTIVE_AGENT_STATUSES = {"queued", "running", "waiting"}
FINAL_AGENT_STATUSES = {"completed", "failed", "cancelled"}
AGENT_STATUSES = ACTIVE_AGENT_STATUSES | FINAL_AGENT_STATUSES


class AgentTrackingError(RuntimeError):
    """Raised when agent lifecycle records cannot be managed safely."""


def guard_agent_updates(*allowed_fields: str):
    allowed = set(allowed_fields)

    def decorator(func):
        @wraps(func)
        def wrapper(repo_root: Path, config: TaskflowConfig, task_id: str, agent_id: str, **changes):
            unknown_fields = find_unknown_fields(changes, allowed)
            if unknown_fields:
                names = ", ".join(unknown_fields)
                raise AgentTrackingError(f"unknown agent update field(s): {names}")
            if "status" in changes and changes["status"] is not None:
                _validate_status(str(changes["status"]))
            return func(repo_root, config, task_id, agent_id, **changes)

        return wrapper

    return decorator


def register_agent(
    repo_root: Path,
    config: TaskflowConfig,
    task_id: str,
    agent_id: str,
    role: str,
    provider: str | None = None,
    current_step: str | None = None,
    last_message_summary: str | None = None,
    owned_paths: list[str] | None = None,
    command: list[str] | None = None,
    status: str = "running",
) -> dict:
    _validate_agent_id(agent_id)
    _validate_status(status)
    _ensure_task_exists(repo_root, config, task_id)

    agent_file = _agent_file(repo_root, config.task_dir, task_id, agent_id)
    if agent_file.exists():
        raise AgentTrackingError(f"agent already exists: {agent_id}")

    now = utc_now()
    agent = {
        "agent_id": agent_id,
        "parent_task_id": task_id,
        "role": role,
        "provider": provider,
        "status": status,
        "current_step": current_step,
        "last_message_summary": last_message_summary,
        "owned_paths": owned_paths or [],
        "command": command or [],
        "pid": None,
        "started_at": now,
        "updated_at": now,
        "finished_at": now if status in FINAL_AGENT_STATUSES else None,
        "last_heartbeat_at": now,
        "error": None,
    }
    _save_agent_record(agent_file, agent)
    return agent


@guard_agent_updates(
    "status",
    "provider",
    "current_step",
    "last_message_summary",
    "owned_paths",
    "command",
    "pid",
    "error",
)
def update_agent(
    repo_root: Path,
    config: TaskflowConfig,
    task_id: str,
    agent_id: str,
    **changes: object,
) -> dict:
    agent, agent_file = load_agent_record(repo_root, config, task_id, agent_id, stale_after_seconds=None)
    agent.pop("raw_status", None)
    persisted_status = str(changes.get("status") or agent["status"])
    _apply_agent_changes(agent, changes)

    now = utc_now()
    agent["updated_at"] = now
    if persisted_status in ACTIVE_AGENT_STATUSES:
        agent["last_heartbeat_at"] = now
        agent["finished_at"] = None
    elif agent.get("finished_at") is None:
        agent["finished_at"] = now
        agent["pid"] = None

    _save_agent_record(agent_file, agent)
    return agent


def load_agent_record(
    repo_root: Path,
    config: TaskflowConfig,
    task_id: str,
    agent_id: str,
    stale_after_seconds: int | None = DEFAULT_STALE_AFTER_SECONDS,
) -> tuple[dict, Path]:
    _validate_agent_id(agent_id)
    agent_file = _agent_file(repo_root, config.task_dir, task_id, agent_id)
    if not agent_file.exists():
        raise FileNotFoundError(f"agent not found: {agent_id}")
    agent = json.loads(agent_file.read_text(encoding="utf-8"))
    return _enrich_agent(agent, stale_after_seconds), agent_file


def list_agents(
    repo_root: Path,
    config: TaskflowConfig,
    *,
    task_id: str | None = None,
    stale_after_seconds: int | None = DEFAULT_STALE_AFTER_SECONDS,
) -> list[dict]:
    agent_files: list[Path] = []
    if task_id:
        root = agent_dir(repo_root, config.task_dir, task_id)
        if root.exists():
            agent_files = sorted(root.glob("*.json"))
    else:
        root = repo_root / config.task_dir
        if root.exists():
            agent_files = sorted(root.glob("*/agents/*.json"))

    agents: list[dict] = []
    for agent_file in agent_files:
        try:
            raw = json.loads(agent_file.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        agents.append(_enrich_agent(raw, stale_after_seconds))

    return sorted(
        agents,
        key=lambda agent: (
            agent.get("updated_at", ""),
            agent.get("started_at", ""),
            agent.get("agent_id", ""),
        ),
        reverse=True,
    )


def _ensure_task_exists(repo_root: Path, config: TaskflowConfig, task_id: str) -> None:
    load_task_record(repo_root=repo_root, task_dir_name=config.task_dir, task_id=task_id)


def _agent_file(repo_root: Path, task_dir_name: str, task_id: str, agent_id: str) -> Path:
    return agent_dir(repo_root, task_dir_name, task_id) / f"{agent_id}.json"


def _save_agent_record(agent_file: Path, agent: dict) -> None:
    agent_file.parent.mkdir(parents=True, exist_ok=True)
    agent_file.write_text(json.dumps(agent, indent=2) + "\n", encoding="utf-8")


def _enrich_agent(agent: dict, stale_after_seconds: int | None) -> dict:
    enriched = dict(agent)
    raw_status = agent.get("status", "running")
    enriched["raw_status"] = raw_status
    enriched["status"] = _derived_status(agent, stale_after_seconds)
    return enriched


def _derived_status(agent: dict, stale_after_seconds: int | None) -> str:
    status = agent.get("status", "running")
    if stale_after_seconds is None or status not in ACTIVE_AGENT_STATUSES:
        return status

    heartbeat = agent.get("last_heartbeat_at") or agent.get("updated_at")
    if not heartbeat:
        return "stale"

    try:
        last_seen = datetime.fromisoformat(heartbeat.replace("Z", "+00:00"))
    except ValueError:
        return "stale"

    age_seconds = (datetime.now(timezone.utc) - last_seen).total_seconds()
    if age_seconds > stale_after_seconds:
        return "stale"
    return status


def _validate_status(status: str) -> None:
    if status not in AGENT_STATUSES:
        allowed = ", ".join(sorted(AGENT_STATUSES))
        raise AgentTrackingError(f"invalid agent status `{status}`; expected one of: {allowed}")


def _validate_agent_id(agent_id: str) -> None:
    invalid_markers = {"/", "\\", ".."}
    if not agent_id or any(marker in agent_id for marker in invalid_markers):
        raise AgentTrackingError(f"invalid agent id: {agent_id}")


def _apply_agent_changes(agent: dict, changes: dict[str, object]) -> None:
    for field, value in changes.items():
        if value is None:
            continue
        agent[field] = value
