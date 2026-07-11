from __future__ import annotations

import json
from pathlib import Path

from ....config import SisyphusConfig
from ....planning import (
    approve_task_plan,
    freeze_task_spec,
    generate_subtasks,
    request_plan_changes,
    revise_task_plan,
)
from ....spec_validation import validate_task_spec


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
    if outcome.gates:
        print("gates:")
        for gate in outcome.gates:
            print(f"- {gate['code']}: {gate['message']}")
    return 1 if outcome.task_status == "blocked" else 0


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
    return 0 if outcome.spec_status == "frozen" and outcome.task_status != "blocked" else 1


def handle_spec_validate(
    *,
    repo_root: Path,
    config: SisyphusConfig,
    task_id: str,
    as_json: bool,
) -> int:
    outcome = validate_task_spec(
        repo_root=repo_root,
        config=config,
        task_id=task_id,
        persist=True,
    )
    if as_json:
        print(json.dumps(outcome.report, indent=2))
        return 1 if outcome.status == "failed" else 0

    print(f"spec_validation {outcome.task_id}")
    print(f"status: {outcome.status}")
    print(f"report: {outcome.report_path}")
    summary = outcome.report.get("summary", {})
    print(f"errors: {summary.get('error_count', 0)}")
    print(f"warnings: {summary.get('warning_count', 0)}")
    findings = outcome.report.get("findings", [])
    if findings:
        print("findings:")
        for finding in findings:
            print(f"- {finding['severity']} {finding['code']}: {finding['message']}")
    else:
        print("findings: none")
    return 1 if outcome.status == "failed" else 0


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
    "handle_spec_validate",
    "handle_subtasks_generate",
]
