from __future__ import annotations

from pathlib import Path

from ....config import SisyphusConfig
from ....planning import (
    approve_task_plan,
    freeze_task_spec,
    generate_subtasks,
    request_plan_changes,
    revise_task_plan,
)


def handle_plan_approve(
    *,
    repo_root: Path,
    config: SisyphusConfig,
    task_id: str,
    reviewer: str,
    notes: str | None,
) -> int:
    outcome = approve_task_plan(
        repo_root=repo_root,
        config=config,
        task_id=task_id,
        reviewer=reviewer,
        notes=notes,
    )
    print(f"plan {outcome.task_id}")
    print(f"plan_status: {outcome.plan_status}")
    print(f"task_status: {outcome.task_status}")
    return 0


def handle_plan_request_changes(
    *,
    repo_root: Path,
    config: SisyphusConfig,
    task_id: str,
    reviewer: str,
    notes: str | None,
) -> int:
    outcome = request_plan_changes(
        repo_root=repo_root,
        config=config,
        task_id=task_id,
        reviewer=reviewer,
        notes=notes,
    )
    print(f"plan {outcome.task_id}")
    print(f"plan_status: {outcome.plan_status}")
    print(f"task_status: {outcome.task_status}")
    if outcome.gates:
        print("gates:")
        for gate in outcome.gates:
            print(f"- {gate['code']}: {gate['message']}")
    return 0


def handle_plan_revise(
    *,
    repo_root: Path,
    config: SisyphusConfig,
    task_id: str,
    author: str,
    notes: str | None,
) -> int:
    outcome = revise_task_plan(
        repo_root=repo_root,
        config=config,
        task_id=task_id,
        author=author,
        notes=notes,
    )
    print(f"plan {outcome.task_id}")
    print(f"plan_status: {outcome.plan_status}")
    print(f"task_status: {outcome.task_status}")
    return 0


def handle_spec_freeze(
    *,
    repo_root: Path,
    config: SisyphusConfig,
    task_id: str,
    reviewer: str,
    notes: str | None,
) -> int:
    outcome = freeze_task_spec(
        repo_root=repo_root,
        config=config,
        task_id=task_id,
        reviewer=reviewer,
        notes=notes,
    )
    print(f"spec {outcome.task_id}")
    print(f"spec_status: {outcome.spec_status}")
    print(f"task_status: {outcome.task_status}")
    print(f"workflow_phase: {outcome.workflow_phase}")
    return 0


def handle_subtasks_generate(*, repo_root: Path, config: SisyphusConfig, task_id: str) -> int:
    outcome = generate_subtasks(
        repo_root=repo_root,
        config=config,
        task_id=task_id,
    )
    print(f"subtasks {outcome.task_id}")
    print(f"count: {len(outcome.subtasks)}")
    print(f"workflow_phase: {outcome.workflow_phase}")
    return 0


__all__ = [
    "handle_plan_approve",
    "handle_plan_request_changes",
    "handle_plan_revise",
    "handle_spec_freeze",
    "handle_subtasks_generate",
]
