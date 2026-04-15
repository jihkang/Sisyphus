from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import subprocess

from .bus import build_event_publisher
from .config import TaskflowConfig
from .events import new_event_envelope
from .planning import collect_plan_gates
from .state import edit_task_record, task_record_path
from .utils import utc_now


@dataclass(slots=True)
class CloseOutcome:
    task_id: str
    status: str
    closed: bool
    allow_dirty: bool
    gates: list[dict]


def run_close(repo_root: Path, config: TaskflowConfig, task_id: str, allow_dirty: bool) -> CloseOutcome:
    task_file = task_record_path(repo_root, config.task_dir, task_id)
    with edit_task_record(task_file) as task:
        gates = [gate for gate in task.get("gates", []) if gate.get("source") not in {"close", "plan"}]
        gates.extend(collect_plan_gates(task, action="close"))

        if task.get("verify_status") != "passed":
            gates.append(_gate("VERIFY_REQUIRED", "task must pass verify before close", source="close"))

        dirty = is_dirty_worktree(_resolve_dirty_check_path(repo_root=repo_root, task=task))
        if dirty and not allow_dirty:
            gates.append(_gate("DIRTY_WORKTREE", "working tree is dirty", source="close"))

        if dirty and allow_dirty:
            task.setdefault("meta", {})["close_override_used"] = True

        gates = _dedupe_gates(gates)
        task["gates"] = gates

        if gates:
            task["status"] = "blocked"
            task["stage"] = "plan_review" if any(gate.get("source") == "plan" for gate in gates) else "audit"
            closed = False
        else:
            task["status"] = "closed"
            task["stage"] = "done"
            task["closed_at"] = utc_now()
            closed = True

    build_event_publisher(repo_root, config).publish(
        new_event_envelope(
            "close.completed",
            source={"module": "closeout"},
            data={
                "task_id": task["id"],
                "closed": closed,
                "status": task["status"],
                "gate_count": 0 if closed else len(gates),
            },
        )
    )
    return CloseOutcome(
        task_id=task["id"],
        status=task["status"],
        closed=closed,
        allow_dirty=allow_dirty,
        gates=[] if closed else gates,
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
    except (subprocess.CalledProcessError, FileNotFoundError, NotADirectoryError, OSError):
        return False


def _resolve_dirty_check_path(repo_root: Path, task: dict) -> Path:
    candidates = [
        task.get("worktree_path"),
        task.get("repo_root"),
        str(repo_root),
    ]
    for candidate in candidates:
        if not candidate:
            continue
        resolved = Path(candidate)
        if resolved.is_dir():
            return resolved
    return repo_root


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
