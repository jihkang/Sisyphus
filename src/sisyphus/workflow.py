from __future__ import annotations

from pathlib import Path

from .audit import run_verify
from .bus import build_event_publisher
from .closeout import run_close
from .conformance import (
    CONFORMANCE_RED,
    append_conformance_log_markdown,
    build_execution_contract,
    run_post_execution_conformance_check,
    run_pre_execution_conformance_check,
    summarize_task_conformance,
)
from .config import SisyphusConfig
from .events import new_event_envelope
from .artifact_snapshot import materialize_feature_task_artifact_snapshot
from .metrics import publish_manual_intervention_required
from .obligation_runtime import execute_next_feature_change_obligation, materialize_feature_change_obligation_queue
from .planning import (
    PLAN_APPROVED,
    current_plan_status,
    current_spec_status,
    freeze_task_spec,
    generate_subtasks,
)
from .provider_wrapper import run_provider_wrapper
from .state import list_task_records, load_task_record, save_task_record


PLANNER_ROLE = "planner"
WORKER_ROLE = "worker"
REVIEWER_ROLE = "reviewer"


def run_workflow_cycle(repo_root: Path, config: SisyphusConfig) -> int:
    progressed = 0
    tasks = list_task_records(repo_root=repo_root, task_dir_name=config.task_dir)
    tasks = sorted(tasks, key=lambda task: (task.get("updated_at", ""), task.get("id", "")))
    for task in tasks:
        if _advance_task(repo_root=repo_root, config=config, task_id=task["id"]):
            progressed += 1
    return progressed


def _advance_task(repo_root: Path, config: SisyphusConfig, task_id: str) -> bool:
    task, _ = load_task_record(repo_root=repo_root, task_dir_name=config.task_dir, task_id=task_id)
    phase = str(task.get("workflow_phase") or "")
    if not bool(task.get("meta", {}).get("auto_loop_enabled", True)):
        return False

    if task.get("status") == "closed":
        return False
    if phase in {"needs_user_input", "promotion_pending", "retarget_required"}:
        return False

    plan_status = current_plan_status(task)
    if plan_status != PLAN_APPROVED:
        return False

    if current_spec_status(task) != "frozen":
        freeze_task_spec(
            repo_root=repo_root,
            config=config,
            task_id=task_id,
            reviewer="workflow-daemon",
            notes="automatic spec freeze after plan approval",
        )
        return True

    if task.get("type") == "feature":
        snapshot = materialize_feature_task_artifact_snapshot(
            repo_root=repo_root,
            config=config,
            task_id=task_id,
        )
        materialized = materialize_feature_change_obligation_queue(
            repo_root=repo_root,
            config=config,
            task_id=task_id,
        )
        if snapshot.changed or materialized.changed:
            return True
        execution = execute_next_feature_change_obligation(
            repo_root=repo_root,
            config=config,
            task_id=task_id,
        )
        if execution.executed:
            return True
        latest_task, _ = load_task_record(repo_root=repo_root, task_dir_name=config.task_dir, task_id=task_id)
        latest_phase = str(latest_task.get("workflow_phase") or "")
        if latest_task.get("status") == "verified" or latest_phase == "verified":
            return False

    if not task.get("subtasks"):
        generate_subtasks(repo_root=repo_root, config=config, task_id=task_id)
        return True

    queued = next((subtask for subtask in task.get("subtasks", []) if subtask.get("status") == "queued"), None)
    if queued:
        return _run_subtask(repo_root=repo_root, config=config, task=task, subtask_id=str(queued["id"]))

    if any(subtask.get("status") == "failed" for subtask in task.get("subtasks", [])):
        _update_workflow_phase(repo_root=repo_root, config=config, task_id=task_id, phase="needs_user_input")
        return True

    if all(subtask.get("status") == "completed" for subtask in task.get("subtasks", [])):
        _update_workflow_phase(repo_root=repo_root, config=config, task_id=task_id, phase="integration_review")
        outcome = run_verify(repo_root=repo_root, config=config, task_id=task_id)
        if outcome.gates:
            _update_workflow_phase(repo_root=repo_root, config=config, task_id=task_id, phase="needs_user_input")
            return True
        close_outcome = run_close(repo_root=repo_root, config=config, task_id=task_id, allow_dirty=True)
        if close_outcome.closed:
            _update_workflow_phase(repo_root=repo_root, config=config, task_id=task_id, phase="closed")
        else:
            latest_task, _ = load_task_record(repo_root=repo_root, task_dir_name=config.task_dir, task_id=task_id)
            next_phase = str(latest_task.get("workflow_phase") or "needs_user_input")
            _update_workflow_phase(repo_root=repo_root, config=config, task_id=task_id, phase=next_phase)
        return True

    return False

def _run_subtask(repo_root: Path, config: SisyphusConfig, task: dict, subtask_id: str) -> bool:
    publisher = build_event_publisher(repo_root, config)
    subtask = next(item for item in task.get("subtasks", []) if str(item.get("id")) == subtask_id)
    pre_status, pre_summary = run_pre_execution_conformance_check(
        task,
        subtask_id=subtask_id,
        source="workflow.pre_exec",
    )
    task_file = repo_root / str(task["task_dir"]) / "task.json"
    save_task_record(task_file=task_file, task=task)
    append_conformance_log_markdown(task, task_file.parent)
    publisher.publish(
        new_event_envelope(
            f"conformance.pre_exec.{pre_status}",
            source={"module": "workflow", "checkpoint": "pre_exec"},
            data={"task_id": task["id"], "subtask_id": subtask_id, "summary": pre_summary},
        )
    )
    if pre_status == CONFORMANCE_RED:
        _update_subtask_status(
            repo_root=repo_root,
            config=config,
            task_id=str(task["id"]),
            subtask_id=subtask_id,
            status="failed",
        )
        _update_workflow_phase(repo_root=repo_root, config=config, task_id=str(task["id"]), phase="needs_user_input")
        return True

    _update_subtask_status(
        repo_root=repo_root,
        config=config,
        task_id=str(task["id"]),
        subtask_id=subtask_id,
        status="in_progress",
    )
    publisher.publish(
        new_event_envelope(
            "subtask.started",
            source={"module": "workflow"},
            data={"task_id": task["id"], "subtask_id": subtask_id, "title": subtask.get("title")},
        )
    )
    exit_code = _run_phase_agent(
        repo_root=repo_root,
        task=task,
        agent_id=subtask_id,
        role=WORKER_ROLE,
        instruction=(
            f"Work only on subtask `{subtask.get('title')}` in category `{subtask.get('category')}`. "
            "Keep other planned work untouched unless required by tests.\n\n"
            f"{build_execution_contract(task, subtask)}"
        ),
    )
    task, task_file = load_task_record(repo_root=repo_root, task_dir_name=config.task_dir, task_id=str(task["id"]))
    post_status, post_summary = run_post_execution_conformance_check(
        task,
        subtask_id=subtask_id,
        exit_code=exit_code,
        source="workflow.post_exec",
    )
    save_task_record(task_file=task_file, task=task)
    append_conformance_log_markdown(task, task_file.parent)
    _update_subtask_status(
        repo_root=repo_root,
        config=config,
        task_id=str(task["id"]),
        subtask_id=subtask_id,
        status="completed" if exit_code == 0 else "failed",
    )
    publisher.publish(
        new_event_envelope(
            f"conformance.post_exec.{post_status}",
            source={"module": "workflow", "checkpoint": "post_exec"},
            data={"task_id": task["id"], "subtask_id": subtask_id, "summary": post_summary},
        )
    )
    publisher.publish(
        new_event_envelope(
            "subtask.completed" if exit_code == 0 else "subtask.failed",
            source={"module": "workflow"},
            data={
                "task_id": task["id"],
                "subtask_id": subtask_id,
                "title": subtask.get("title"),
                "exit_code": exit_code,
                "conformance_status": post_status,
            },
        )
    )
    if exit_code != 0 or post_status == CONFORMANCE_RED:
        _update_workflow_phase(repo_root=repo_root, config=config, task_id=str(task["id"]), phase="needs_user_input")
    return True


def _run_phase_agent(*, repo_root: Path, task: dict, agent_id: str, role: str, instruction: str) -> int:
    provider = str(task.get("meta", {}).get("default_provider") or "codex")
    return run_provider_wrapper(
        provider,
        [
            str(task["id"]),
            agent_id,
            "--role",
            role,
            "--instruction",
            instruction,
        ],
        repo_root=repo_root,
    )

def _update_workflow_phase(repo_root: Path, config: SisyphusConfig, task_id: str, *, phase: str) -> None:
    task, task_file = load_task_record(repo_root=repo_root, task_dir_name=config.task_dir, task_id=task_id)
    task["workflow_phase"] = phase
    if phase == "needs_user_input":
        task["status"] = "blocked"
    save_task_record(task_file=task_file, task=task)
    build_event_publisher(repo_root, config).publish(
        new_event_envelope(
            "task.updated",
            source={"module": "workflow", "action": "update_phase"},
            data={
                "task_id": task_id,
                "workflow_phase": phase,
                "status": task.get("status"),
                "conformance_status": summarize_task_conformance(task).get("status"),
            },
        )
    )
    if phase == "needs_user_input":
        publish_manual_intervention_required(
            repo_root,
            config,
            task_id=task_id,
            reason="workflow_needs_user_input",
            workflow_phase=phase,
            status=str(task.get("status") or ""),
            detail="workflow paused and requires operator input before continuing",
        )


def _update_subtask_status(
    repo_root: Path,
    config: SisyphusConfig,
    task_id: str,
    subtask_id: str,
    *,
    status: str,
) -> None:
    task, task_file = load_task_record(repo_root=repo_root, task_dir_name=config.task_dir, task_id=task_id)
    subtasks = list(task.get("subtasks", []))
    for subtask in subtasks:
        if str(subtask.get("id")) != subtask_id:
            continue
        subtask["status"] = status
        break
    task["subtasks"] = subtasks
    save_task_record(task_file=task_file, task=task)
