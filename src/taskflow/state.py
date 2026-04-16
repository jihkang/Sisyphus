from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
import json
import os
import tempfile
from typing import TextIO

from .conformance import default_task_conformance, ensure_task_conformance_defaults
from .config import SisyphusConfig
from .gitops import branch_name, worktree_path
from .paths import task_dir
from .utils import utc_now


if os.name == "nt":
    import msvcrt
else:
    import fcntl


def task_id_for(task_type: str, slug: str, now: datetime | None = None) -> str:
    current = now or datetime.now(timezone.utc)
    return f"TF-{current:%Y%m%d}-{task_type}-{slug}"


def create_task_record(
    repo_root: Path,
    config: SisyphusConfig,
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
    config: SisyphusConfig,
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
        "conformance": default_task_conformance(),
        "docs": docs,
        "meta": {
            "sequence": None,
            "close_override_used": False,
        },
    }


def task_record_path(repo_root: Path, task_dir_name: str, task_id: str) -> Path:
    return task_dir(repo_root, task_dir_name, task_id) / "task.json"


def load_task_record(repo_root: Path, task_dir_name: str, task_id: str) -> tuple[dict, Path]:
    task_file = task_record_path(repo_root, task_dir_name, task_id)
    if not task_file.exists():
        raise FileNotFoundError(f"task not found: {task_id}")
    task = json.loads(task_file.read_text(encoding="utf-8"))
    return ensure_task_record_defaults(task), task_file


def list_task_records(repo_root: Path, task_dir_name: str) -> list[dict]:
    root = repo_root / task_dir_name
    if not root.exists():
        return []

    tasks: list[dict] = []
    for task_file in sorted(root.glob("*/task.json")):
        try:
            task = json.loads(task_file.read_text(encoding="utf-8"))
            tasks.append(ensure_task_record_defaults(task))
        except json.JSONDecodeError:
            continue
    return tasks


def save_task_record(task_file: Path, task: dict) -> None:
    with _task_file_lock(task_file):
        _save_task_record_locked(task_file=task_file, task=task)


@contextmanager
def edit_task_record(task_file: Path) -> Iterator[dict]:
    if not task_file.exists():
        raise FileNotFoundError(f"task not found: {task_file}")
    with _task_file_lock(task_file):
        task = json.loads(task_file.read_text(encoding="utf-8"))
        ensure_task_record_defaults(task)
        yield task
        _save_task_record_locked(task_file=task_file, task=task)


def ensure_task_record_defaults(task: dict) -> dict:
    task.setdefault("id", None)
    task.setdefault("type", None)
    task.setdefault("slug", None)
    task.setdefault("status", "open")
    task.setdefault("stage", "spec")
    task.setdefault("plan_status", "pending_review")
    task.setdefault("plan_reviewed_at", None)
    task.setdefault("plan_reviewed_by", None)
    task.setdefault("plan_review_notes", None)
    task.setdefault("plan_review_round", 0)
    task.setdefault("max_plan_review_rounds", 3)
    task.setdefault("plan_review_history", [])
    task.setdefault("workflow_phase", "plan_in_review")
    task.setdefault("spec_status", "draft")
    task.setdefault("spec_frozen_at", None)
    task.setdefault("spec_reviewed_by", None)
    task.setdefault("spec_review_notes", None)
    task.setdefault("audit_attempts", 0)
    task.setdefault("max_audit_attempts", 10)
    task.setdefault("created_at", utc_now())
    task.setdefault("updated_at", utc_now())
    task.setdefault("closed_at", None)
    task.setdefault("repo_root", "")
    task.setdefault("task_dir", "")
    task.setdefault("worktree_path", "")
    task.setdefault("branch", None)
    task.setdefault("base_branch", None)
    task.setdefault("verify_profile", "default")
    task.setdefault("verify_commands", [])
    task.setdefault("verify_status", "not_run")
    task.setdefault("last_verified_at", None)
    task.setdefault("last_verify_results", [])
    task.setdefault("test_strategy", {})
    task.setdefault("gates", [])
    task.setdefault("subtasks", [])
    if not isinstance(task.get("conformance"), dict):
        task["conformance"] = default_task_conformance()
    task.setdefault("docs", {})
    if not isinstance(task.get("meta"), dict):
        task["meta"] = {"sequence": None, "close_override_used": False}
    else:
        task["meta"].setdefault("sequence", None)
        task["meta"].setdefault("close_override_used", False)
    ensure_task_conformance_defaults(task)
    return task


def sync_task_support_files(task: dict) -> None:
    repo_root = Path(str(task.get("repo_root", "")))
    worktree_path = Path(str(task.get("worktree_path", "")))
    task_dir_value = task.get("task_dir")
    if not task_dir_value or not repo_root.is_dir() or not worktree_path.is_dir():
        return

    source_task_dir = repo_root / str(task_dir_value)
    target_task_dir = worktree_path / str(task_dir_value)
    if not source_task_dir.exists():
        return

    target_task_dir.mkdir(parents=True, exist_ok=True)
    relative_paths = ["task.json", *[str(path) for path in task.get("docs", {}).values() if path]]
    for relative_path in relative_paths:
        source_path = source_task_dir / relative_path
        if not source_path.exists():
            continue
        target_path = target_task_dir / relative_path
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_text(source_path.read_text(encoding="utf-8"), encoding="utf-8")


def _save_task_record_locked(task_file: Path, task: dict) -> None:
    ensure_task_record_defaults(task)
    task["updated_at"] = utc_now()
    _write_task_record_atomically(task_file, json.dumps(task, indent=2) + "\n")
    sync_task_support_files(task)


def _write_task_record_atomically(task_file: Path, payload: str) -> None:
    task_file.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            dir=task_file.parent,
            prefix=f".{task_file.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
            temporary_path = Path(handle.name)
        os.replace(temporary_path, task_file)
    finally:
        if temporary_path is not None and temporary_path.exists():
            temporary_path.unlink(missing_ok=True)


@contextmanager
def _task_file_lock(task_file: Path) -> Iterator[None]:
    lock_path = task_file.parent / f"{task_file.name}.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a+", encoding="utf-8") as lock_handle:
        _prime_lock_file(lock_handle)
        _acquire_lock(lock_handle)
        try:
            yield
        finally:
            _release_lock(lock_handle)


def _prime_lock_file(lock_handle: TextIO) -> None:
    lock_handle.seek(0)
    if lock_handle.read(1):
        lock_handle.seek(0)
        return
    lock_handle.seek(0)
    lock_handle.write("0")
    lock_handle.flush()
    lock_handle.seek(0)


def _acquire_lock(lock_handle: TextIO) -> None:
    lock_handle.seek(0)
    if os.name == "nt":
        msvcrt.locking(lock_handle.fileno(), msvcrt.LK_LOCK, 1)
        return
    fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX)


def _release_lock(lock_handle: TextIO) -> None:
    lock_handle.seek(0)
    if os.name == "nt":
        msvcrt.locking(lock_handle.fileno(), msvcrt.LK_UNLCK, 1)
        return
    fcntl.flock(lock_handle.fileno(), fcntl.LOCK_UN)
