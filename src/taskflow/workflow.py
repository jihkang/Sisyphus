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
from .config import TaskflowConfig
from .events import new_event_envelope
from .planning import (
    PLAN_APPROVED,
    current_plan_status,
    current_spec_status,
    freeze_task_spec,
    generate_subtasks,
)
from .provider_wrapper import run_provider_wrapper
from .state import edit_task_record, list_task_records, load_task_record, task_record_path


PLANNER_ROLE = "planner"
WORKER_ROLE = "worker"
REVIEWER_ROLE = "reviewer"


def run_workflow_cycle(repo_root: Path, config: TaskflowConfig) -> int:
    progressed = 0
    tasks = list_task_records(repo_root=repo_root, task_dir_name=config.task_dir)
    tasks = sorted(tasks, key=lambda task: (task.get("updated_at", ""), task.get("id", "")))
    for task in tasks:
        if _advance_task(repo_root=repo_root, config=config, task_id=task["id"]):
            progressed += 1
    return progressed


def _advance_task(repo_root: Path, config: TaskflowConfig, task_id: str) -> bool:
    task, _ = load_task_record(repo_root=repo_root, task_dir_name=config.task_dir, task_id=task_id)
    phase = str(task.get("workflow_phase") or "")
    if not bool(task.get("meta", {}).get("auto_loop_enabled", True)):
        return False

    if task.get("status") == "closed":
        return False
    if phase == "needs_user_input":
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
            _update_workflow_phase(repo_root=repo_root, config=config, task_id=task_id, phase="needs_user_input")
        return True

    return False

def _run_subtask(repo_root: Path, config: TaskflowConfig, task: dict, subtask_id: str) -> bool:
    publisher = build_event_publisher(repo_root, config)
    task_file = task_record_path(repo_root, config.task_dir, str(task["id"]))
    with edit_task_record(task_file) as task:
        subtask = next(item for item in task.get("subtasks", []) if str(item.get("id")) == subtask_id)
        pre_status, pre_summary = run_pre_execution_conformance_check(
            task,
            subtask_id=subtask_id,
            source="workflow.pre_exec",
        )
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
    with edit_task_record(task_file) as task:
        post_status, post_summary = run_post_execution_conformance_check(
            task,
            subtask_id=subtask_id,
            exit_code=exit_code,
            source="workflow.post_exec",
        )
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

def _update_workflow_phase(repo_root: Path, config: TaskflowConfig, task_id: str, *, phase: str) -> None:
    task_file = task_record_path(repo_root, config.task_dir, task_id)
    with edit_task_record(task_file) as task:
        task["workflow_phase"] = phase
        if phase == "needs_user_input":
            task["status"] = "blocked"
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


def _update_subtask_status(
    repo_root: Path,
    config: TaskflowConfig,
    task_id: str,
    subtask_id: str,
    *,
    status: str,
) -> None:
    task_file = task_record_path(repo_root, config.task_dir, task_id)
    with edit_task_record(task_file) as task:
        subtasks = list(task.get("subtasks", []))
        for subtask in subtasks:
            if str(subtask.get("id")) != subtask_id:
                continue
            subtask["status"] = status
            break
        task["subtasks"] = subtasks
