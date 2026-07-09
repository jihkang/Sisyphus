from __future__ import annotations

from pathlib import Path


def planning_dir(repo_root: Path) -> Path:
    return repo_root / ".planning"


def task_dir(repo_root: Path, task_dir_name: str, task_id: str) -> Path:
    return repo_root / task_dir_name / task_id


def agent_dir(repo_root: Path, task_dir_name: str, task_id: str) -> Path:
    return task_dir(repo_root, task_dir_name, task_id) / "agents"


def inbox_dir(repo_root: Path) -> Path:
    return planning_dir(repo_root) / "inbox"


def inbox_pending_dir(repo_root: Path) -> Path:
    return inbox_dir(repo_root) / "pending"


def inbox_processed_dir(repo_root: Path) -> Path:
    return inbox_dir(repo_root) / "processed"


def inbox_failed_dir(repo_root: Path) -> Path:
    return inbox_dir(repo_root) / "failed"


def event_log_file(repo_root: Path) -> Path:
    return planning_dir(repo_root) / "events.jsonl"
