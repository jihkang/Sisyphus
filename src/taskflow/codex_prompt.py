from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import json

from .config import TaskflowConfig
from .state import load_task_record
from .utils import project_fields


@dataclass(slots=True)
class CodexPrompt:
    task_id: str
    workdir: Path
    prompt: str


def build_codex_prompt(
    repo_root: Path,
    config: TaskflowConfig,
    task_id: str,
    *,
    extra_instruction: str | None = None,
) -> CodexPrompt:
    task, task_file = load_task_record(repo_root=repo_root, task_dir_name=config.task_dir, task_id=task_id)
    task_dir = task_file.parent
    workdir = _resolve_workdir(repo_root=repo_root, task=task)
    docs = _load_docs(task=task, task_dir=task_dir)
    task_snapshot = _build_task_snapshot(task)

    sections = [
        "You are the local Codex worker for this task.",
        "Read the task metadata and docs below, inspect the repository state in the assigned worktree, then carry out the task.",
        "Keep changes aligned with the documented acceptance criteria and test strategy.",
        "If the task docs and code disagree, prefer the task docs and update code accordingly.",
        "Run relevant validation before finishing when feasible.",
        "Task docs live under the repository-relative paths shown in each section heading.",
        "Start your final response with exactly one status line: `STATUS: completed`, `STATUS: blocked`, or `STATUS: failed`.",
    ]
    if extra_instruction:
        sections.append(f"Additional operator instruction: {extra_instruction}")

    body = [
        "\n".join(sections),
        "## Task Metadata",
        json.dumps(task_snapshot, indent=2),
    ]

    for name, content in docs:
        body.extend(
            [
                f"## {name}",
                content.strip(),
            ]
        )

    return CodexPrompt(
        task_id=task["id"],
        workdir=workdir,
        prompt="\n\n".join(body).strip() + "\n",
    )


def _resolve_workdir(repo_root: Path, task: dict) -> Path:
    worktree_path = Path(str(task.get("worktree_path", "")))
    if worktree_path.is_dir():
        return worktree_path
    return repo_root


def _load_docs(task: dict, task_dir: Path) -> list[tuple[str, str]]:
    docs: list[tuple[str, str]] = []
    task_dir_relative = Path(str(task.get("task_dir", "")))
    for key, relative_path in task.get("docs", {}).items():
        if not relative_path:
            continue
        path = task_dir / relative_path
        if not path.exists():
            continue
        display_path = (task_dir_relative / relative_path).as_posix() if str(task_dir_relative) != "." else relative_path
        label = f"{key.upper()} ({display_path})"
        docs.append((label, path.read_text(encoding="utf-8")))
    return docs


def _build_task_snapshot(task: dict) -> dict[str, object]:
    return project_fields(
        task,
        {
            "id": None,
            "type": None,
            "slug": None,
            "status": None,
            "stage": None,
            "plan_status": None,
            "plan_review_round": None,
            "max_plan_review_rounds": None,
            "plan_reviewed_at": None,
            "plan_reviewed_by": None,
            "workflow_phase": None,
            "spec_status": None,
            "spec_frozen_at": None,
            "branch": None,
            "base_branch": None,
            "worktree_path": None,
            "verify_status": None,
            "subtasks": list,
            "gates": list,
            "test_strategy": dict,
            "docs": dict,
        },
    )
