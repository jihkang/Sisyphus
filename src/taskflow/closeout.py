from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import subprocess

from .config import TaskflowConfig
from .state import load_task_record, save_task_record, utc_now


@dataclass(slots=True)
class CloseOutcome:
    task_id: str
    status: str
    closed: bool
    allow_dirty: bool
    gates: list[dict]


def run_close(repo_root: Path, config: TaskflowConfig, task_id: str, allow_dirty: bool) -> CloseOutcome:
    task, task_file = load_task_record(repo_root=repo_root, task_dir_name=config.task_dir, task_id=task_id)
    gates = list(task.get("gates", []))

    if task.get("verify_status") != "passed":
        gates.append(_gate("VERIFY_REQUIRED", "task must pass verify before close", source="close"))

    dirty = is_dirty_worktree(Path(task.get("repo_root", str(repo_root))))
    if dirty and not allow_dirty:
        gates.append(_gate("DIRTY_WORKTREE", "working tree is dirty", source="close"))

    if dirty and allow_dirty:
        task.setdefault("meta", {})["close_override_used"] = True

    gates = _dedupe_gates(gates)
    task["gates"] = gates

    if gates:
        task["status"] = "blocked"
        task["stage"] = "audit"
        save_task_record(task_file=task_file, task=task)
        return CloseOutcome(
            task_id=task["id"],
            status=task["status"],
            closed=False,
            allow_dirty=allow_dirty,
            gates=gates,
        )

    task["status"] = "closed"
    task["stage"] = "done"
    task["closed_at"] = utc_now()
    save_task_record(task_file=task_file, task=task)
    return CloseOutcome(
        task_id=task["id"],
        status=task["status"],
        closed=True,
        allow_dirty=allow_dirty,
        gates=[],
    )


def is_dirty_worktree(path: Path) -> bool:
    try:
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=path,
            check=True,
            capture_output=True,
            text=True,
        )
        return bool(result.stdout.strip())
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


def _gate(code: str, message: str, source: str) -> dict:
    return {
        "code": code,
        "message": message,
        "blocking": True,
        "source": source,
        "created_at": utc_now(),
    }


def _dedupe_gates(gates: list[dict]) -> list[dict]:
    seen: set[tuple[str, str]] = set()
    deduped: list[dict] = []
    for gate in gates:
        key = (gate.get("code", ""), gate.get("message", ""))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(gate)
    return deduped
