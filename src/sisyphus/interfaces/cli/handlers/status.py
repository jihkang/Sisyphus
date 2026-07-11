from __future__ import annotations

import json
from pathlib import Path

from ....agents import list_agents
from ....config import SisyphusConfig
from ....service import (
    extract_conformance_summary,
    format_conformance_summary,
    summarize_subtask_conformance,
)
from ....state import list_task_records
from ..renderers import project_task_for_status_output


def handle_status(
    *,
    repo_root: Path,
    config: SisyphusConfig,
    as_json: bool,
    only_open: bool,
    only_blocked: bool,
    show_agents: bool,
    stale_after_seconds: int,
) -> int:
    tasks = list_task_records(repo_root=repo_root, task_dir_name=config.task_dir)

    if only_open:
        tasks = [task for task in tasks if task.get("status") in {"open", "in_progress"}]
    if only_blocked:
        tasks = [task for task in tasks if task.get("status") == "blocked"]

    tasks = sorted(
        tasks,
        key=lambda task: (
            task.get("updated_at", ""),
            task.get("created_at", ""),
            task.get("id", ""),
        ),
        reverse=True,
    )

    agents_by_task: dict[str, list[dict]] = {}
    if show_agents:
        for agent in list_agents(
            repo_root=repo_root,
            config=config,
            stale_after_seconds=stale_after_seconds,
        ):
            agents_by_task.setdefault(agent["parent_task_id"], []).append(agent)

    if as_json:
        tasks = [project_task_for_status_output(task) for task in tasks]
        if show_agents:
            tasks = [
                {
                    **task,
                    "agents": agents_by_task.get(task["id"], []),
                }
                for task in tasks
            ]
        print(json.dumps(tasks, indent=2))
        return 0

    if not tasks:
        print("no tasks found")
        return 0

    for task in tasks:
        gate_count = len(task.get("gates", []))
        task_conformance = format_conformance_summary(extract_conformance_summary(task))
        subtask_conformance = summarize_subtask_conformance(task)
        validation = task.get("spec_validation") if isinstance(task.get("spec_validation"), dict) else {}
        validation_text = ""
        if validation.get("status"):
            validation_text = (
                f" spec_validation={validation['status']}"
                f"/{validation.get('error_count', 0)}e"
                f"/{validation.get('warning_count', 0)}w"
            )
        print(
            f"{task.get('id')} "
            f"[{task.get('type')}] "
            f"status={task.get('status')} "
            f"stage={task.get('stage')} "
            f"plan={task.get('plan_status', 'approved')} "
            f"spec={task.get('spec_status', 'frozen')} "
            f"phase={task.get('workflow_phase', '-')} "
            f"audit={task.get('audit_attempts', 0)}/{task.get('max_audit_attempts', 10)} "
            f"gates={gate_count}"
            f"{validation_text}"
            f"{f' conformance={task_conformance}' if task_conformance else ''}"
        )
        if subtask_conformance:
            print(f"  subtask_conformance={subtask_conformance}")
            subtasks = task.get("subtasks")
            if isinstance(subtasks, list):
                for subtask in subtasks:
                    if not isinstance(subtask, dict):
                        continue
                    subtask_conformance_summary = format_conformance_summary(extract_conformance_summary(subtask))
                    if not subtask_conformance_summary:
                        continue
                    print(
                        f"  - {subtask.get('id')} "
                        f"status={subtask.get('status')} "
                        f"conformance={subtask_conformance_summary}"
                    )
        if show_agents:
            task_agents = agents_by_task.get(task["id"], [])
            active_agents = [
                agent for agent in task_agents if agent.get("status") in {"queued", "running", "waiting", "stale"}
            ]
            print(f"  agents={len(task_agents)} active={len(active_agents)}")
            for agent in task_agents:
                step = agent.get("current_step") or "-"
                print(
                    f"  * {agent.get('agent_id')} "
                    f"provider={agent.get('provider') or 'n/a'} "
                    f"role={agent.get('role')} "
                    f"status={agent.get('status')} "
                    f"step={step}"
                )
        if gate_count:
            for gate in task["gates"]:
                print(f"  - {gate.get('code')}: {gate.get('message')}")
    return 0


__all__ = ["handle_status"]
