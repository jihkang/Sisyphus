from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import json

from .config import TaskflowConfig
from .gitops import branch_name, worktree_path
from .paths import task_dir


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def task_id_for(task_type: str, slug: str, now: datetime | None = None) -> str:
    current = now or datetime.now(timezone.utc)
    return f"TF-{current:%Y%m%d}-{task_type}-{slug}"


def create_task_record(
    repo_root: Path,
    config: TaskflowConfig,
    task_type: str,
    slug: str,
) -> dict:
    task = build_task_record(
        repo_root=repo_root,
        config=config,
        task_type=task_type,
        slug=slug,
    )
    task_path = repo_root / task["task_dir"]
    task_path.mkdir(parents=True, exist_ok=True)
    task_file = task_path / "task.json"
    save_task_record(task_file=task_file, task=task)
    return task


def build_task_record(
    repo_root: Path,
    config: TaskflowConfig,
    task_type: str,
    slug: str,
) -> dict:
    task_id = task_id_for(task_type=task_type, slug=slug)
    branch = branch_name(
        task_type=task_type,
        slug=slug,
        feature_prefix=config.branch_prefix_feature,
        issue_prefix=config.branch_prefix_issue,
    )
    task_path = task_dir(repo_root, config.task_dir, task_id)

    verify_profile = task_type if task_type in config.verify else "default"
    verify_keys = config.verify.get(verify_profile, [])
    verify_commands = [config.commands[name] for name in verify_keys if name in config.commands]

    docs = (
        {"brief": "BRIEF.md", "plan": "PLAN.md", "verify": "VERIFY.md", "log": "LOG.md"}
        if task_type == "feature"
        else {
            "brief": "BRIEF.md",
            "repro": "REPRO.md",
            "fix_plan": "FIX_PLAN.md",
            "verify": "VERIFY.md",
            "log": "LOG.md",
        }
    )

    return {
        "id": task_id,
        "type": task_type,
        "slug": slug,
        "status": "open",
        "stage": "spec",
        "plan_status": "pending_review",
        "plan_reviewed_at": None,
        "plan_reviewed_by": None,
        "plan_review_notes": None,
        "plan_review_round": 0,
        "max_plan_review_rounds": 3,
        "plan_review_history": [],
        "workflow_phase": "plan_in_review",
        "spec_status": "draft",
        "spec_frozen_at": None,
        "spec_reviewed_by": None,
        "spec_review_notes": None,
        "audit_attempts": 0,
        "max_audit_attempts": 10,
        "created_at": utc_now(),
        "updated_at": utc_now(),
        "closed_at": None,
        "repo_root": str(repo_root.resolve()),
        "task_dir": str(task_path.relative_to(repo_root)),
        "worktree_path": str(worktree_path(repo_root, config.worktree_root, task_id)),
        "branch": branch,
        "base_branch": config.base_branch,
        "verify_profile": verify_profile,
        "verify_commands": verify_commands,
        "verify_status": "not_run",
        "last_verified_at": None,
        "last_verify_results": [],
        "test_strategy": {
            "normal_cases": [],
            "edge_cases": [],
            "exception_cases": [],
            "verification_methods": [],
            "external_llm": {
                "required": False,
                "provider": None,
                "purpose": None,
                "trigger": None,
                "status": "not_needed",
            },
        },
        "gates": [],
        "subtasks": [],
        "docs": docs,
        "meta": {
            "sequence": None,
            "close_override_used": False,
        },
    }


def load_task_record(repo_root: Path, task_dir_name: str, task_id: str) -> tuple[dict, Path]:
    task_file = task_dir(repo_root, task_dir_name, task_id) / "task.json"
    if not task_file.exists():
        raise FileNotFoundError(f"task not found: {task_id}")
    return json.loads(task_file.read_text(encoding="utf-8")), task_file


def list_task_records(repo_root: Path, task_dir_name: str) -> list[dict]:
    root = repo_root / task_dir_name
    if not root.exists():
        return []

    tasks: list[dict] = []
    for task_file in sorted(root.glob("*/task.json")):
        try:
            tasks.append(json.loads(task_file.read_text(encoding="utf-8")))
        except json.JSONDecodeError:
            continue
    return tasks


def save_task_record(task_file: Path, task: dict) -> None:
    task["updated_at"] = utc_now()
    task_file.write_text(json.dumps(task, indent=2) + "\n", encoding="utf-8")
