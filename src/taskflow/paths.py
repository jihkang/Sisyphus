from __future__ import annotations

from pathlib import Path


def task_dir(repo_root: Path, task_dir_name: str, task_id: str) -> Path:
    return repo_root / task_dir_name / task_id
