from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import subprocess

from .bus import build_event_publisher
from .config import SisyphusConfig
from .evidence_graph import collect_evidence_close_gates
from .events import new_event_envelope
from .gates import dedupe_gates as _dedupe_gates, make_gate as _gate
from .lifecycle_rules import evaluate_transition
from .lifecycle_state import LifecycleAction
from .metrics import publish_manual_intervention_required
from .state import load_task_record, save_task_record, utc_now


@dataclass(slots=True)
class CloseOutcome:
    task_id: str
    status: str
    closed: bool
    allow_dirty: bool
    gates: list[dict]


def run_close(repo_root: Path, config: SisyphusConfig, task_id: str, allow_dirty: bool) -> CloseOutcome:
    task, task_file = load_task_record(repo_root=repo_root, task_dir_name=config.task_dir, task_id=task_id)
    gates = [
        gate
        for gate in task.get("gates", [])
        if gate.get("source") not in {"close", "plan", "conformance", "promotion", "evidence"}
    ]
    transition = evaluate_transition(task, LifecycleAction.CLOSE)
    gates.extend(transition.gates)
    gates.extend(collect_evidence_close_gates(task, task_file.parent))

    dirty = is_dirty_worktree(_resolve_dirty_check_path(repo_root=repo_root, task=task))
    if dirty and not allow_dirty:
        gates.append(_gate("DIRTY_WORKTREE", "working tree is dirty", source="close"))

    if dirty and allow_dirty:
        task.setdefault("meta", {})["close_override_used"] = True

    gates = _dedupe_gates(gates)
    task["gates"] = gates

    if gates:
        close_gate_codes = {gate.get("code") for gate in gates if gate.get("source") == "close"}
        if close_gate_codes == {"PROMOTION_REQUIRED"}:
            task["status"] = "verified"
            task["stage"] = "promotion"
            task["workflow_phase"] = "promotion_pending"
        else:
            task["status"] = "blocked"
            task["stage"] = "plan_review" if any(gate.get("source") == "plan" for gate in gates) else "audit"
        save_task_record(task_file=task_file, task=task)
        build_event_publisher(repo_root, config).publish(
            new_event_envelope(
                "close.completed",
                source={"module": "closeout"},
                data={"task_id": task["id"], "closed": False, "status": task["status"], "gate_count": len(gates)},
            )
        )
        if close_gate_codes == {"PROMOTION_REQUIRED"}:
            publish_manual_intervention_required(
                repo_root,
                config,
                task_id=str(task["id"]),
                reason="promotion_required",
                workflow_phase="promotion_pending",
                status=str(task.get("status") or ""),
                detail="task passed verify but cannot close until promotion is recorded",
            )
        return CloseOutcome(
            task_id=task["id"],
            status=task["status"],
            closed=False,
            allow_dirty=allow_dirty,
            gates=gates,
        )

    task["status"] = "closed"
    task["stage"] = "done"
    task["workflow_phase"] = "closed"
    task["closed_at"] = utc_now()
    save_task_record(task_file=task_file, task=task)
    build_event_publisher(repo_root, config).publish(
        new_event_envelope(
            "close.completed",
            source={"module": "closeout"},
            data={"task_id": task["id"], "closed": True, "status": task["status"], "gate_count": 0},
        )
    )
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
