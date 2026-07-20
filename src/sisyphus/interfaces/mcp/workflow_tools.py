from __future__ import annotations

from types import MappingProxyType
from pathlib import Path

from ...composition.closeout import close_task as run_close
from ...composition.external_review import record_external_review
from ...composition.runtime import run_daemon
from ...composition.verification import verify_task as run_verify
from ...config import SisyphusConfig
from ...composition.planning import (
    approve_task_plan,
    freeze_task_spec,
    generate_subtasks,
    request_plan_changes,
    revise_task_plan,
    validate_task_spec,
)
from ...shared.coerce import optional_str
from .operator_auth import require_operator_capability
from ..agent_queries import list_agents


def _plan_approve(
    *,
    repo_root: Path,
    config: SisyphusConfig,
    args: dict[str, object],
    approve_plan=approve_task_plan,
    **_: object,
) -> dict[str, object]:
    outcome = approve_plan(
        repo_root=repo_root,
        config=config,
        task_id=str(args["task_id"]),
        reviewer=str(args.get("reviewer", "operator")),
        notes=optional_str(args.get("notes")),
    )
    return {
        "task_id": outcome.task_id,
        "plan_status": outcome.plan_status,
        "task_status": outcome.task_status,
        "gates": outcome.gates,
    }


def _plan_request_changes(
    *,
    repo_root: Path,
    config: SisyphusConfig,
    args: dict[str, object],
    request_changes=request_plan_changes,
    **_: object,
) -> dict[str, object]:
    outcome = request_changes(
        repo_root=repo_root,
        config=config,
        task_id=str(args["task_id"]),
        reviewer=str(args.get("reviewer", "operator")),
        notes=optional_str(args.get("notes")),
    )
    return {
        "task_id": outcome.task_id,
        "plan_status": outcome.plan_status,
        "task_status": outcome.task_status,
        "gates": outcome.gates,
    }


def _plan_revise(
    *,
    repo_root: Path,
    config: SisyphusConfig,
    args: dict[str, object],
    revise_plan=revise_task_plan,
    **_: object,
) -> dict[str, object]:
    outcome = revise_plan(
        repo_root=repo_root,
        config=config,
        task_id=str(args["task_id"]),
        author=str(args.get("author", "operator")),
        notes=optional_str(args.get("notes")),
    )
    return {
        "task_id": outcome.task_id,
        "plan_status": outcome.plan_status,
        "task_status": outcome.task_status,
        "gates": outcome.gates,
    }


def _spec_freeze(
    *,
    repo_root: Path,
    config: SisyphusConfig,
    args: dict[str, object],
    freeze_spec=freeze_task_spec,
    **_: object,
) -> dict[str, object]:
    outcome = freeze_spec(
        repo_root=repo_root,
        config=config,
        task_id=str(args["task_id"]),
        reviewer=str(args.get("reviewer", "operator")),
        notes=optional_str(args.get("notes")),
    )
    return {
        "task_id": outcome.task_id,
        "spec_status": outcome.spec_status,
        "task_status": outcome.task_status,
        "workflow_phase": outcome.workflow_phase,
    }


def _spec_validate(
    *,
    repo_root: Path,
    config: SisyphusConfig,
    args: dict[str, object],
    validate_spec_fn=validate_task_spec,
    **_: object,
) -> dict[str, object]:
    outcome = validate_spec_fn(
        repo_root=repo_root,
        config=config,
        task_id=str(args["task_id"]),
        persist=bool(args.get("persist", True)),
    )
    return {
        "task_id": outcome.task_id,
        "status": outcome.status,
        "stale": outcome.stale,
        "report_path": str(outcome.report_path),
        "gates": outcome.gates,
        "report": outcome.report,
    }


def _subtasks_generate(
    *,
    repo_root: Path,
    config: SisyphusConfig,
    args: dict[str, object],
    generate_subtasks_fn=generate_subtasks,
    **_: object,
) -> dict[str, object]:
    outcome = generate_subtasks_fn(repo_root=repo_root, config=config, task_id=str(args["task_id"]))
    return {
        "task_id": outcome.task_id,
        "workflow_phase": outcome.workflow_phase,
        "subtasks": outcome.subtasks,
    }


def _verify_task(
    *,
    repo_root: Path,
    config: SisyphusConfig,
    args: dict[str, object],
    verify_task=run_verify,
    **_: object,
) -> dict[str, object]:
    outcome = verify_task(repo_root=repo_root, config=config, task_id=str(args["task_id"]))
    return {
        "task_id": outcome.task_id,
        "status": outcome.status,
        "stage": outcome.stage,
        "gates": outcome.gates,
        "audit_attempts": outcome.audit_attempts,
    }


def _record_external_review(
    *,
    repo_root: Path,
    config: SisyphusConfig,
    args: dict[str, object],
    record_review=record_external_review,
    **_: object,
) -> dict[str, object]:
    require_operator_capability(args.get("operator_capability"))
    outcome = record_review(
        repo_root=repo_root,
        config=config,
        task_id=str(args["task_id"]),
        envelope_path=str(args["envelope_path"]),
    )
    return {
        "task_id": outcome.task_id,
        "status": outcome.status,
        "provider": outcome.provider,
        "reviewer": outcome.reviewer,
        "reviewed_head_sha": outcome.reviewed_head_sha,
        "scope_digest": outcome.scope_digest,
        "envelope_path": outcome.envelope_path,
        "envelope_digest": outcome.envelope_digest,
        "report_path": outcome.report_path,
        "report_digest": outcome.report_digest,
        "finding_count": outcome.finding_count,
        "blocking_finding_count": outcome.blocking_finding_count,
        "completed_at": outcome.completed_at,
    }


def _close_task(
    *,
    repo_root: Path,
    config: SisyphusConfig,
    args: dict[str, object],
    close_task=run_close,
    **_: object,
) -> dict[str, object]:
    outcome = close_task(
        repo_root=repo_root,
        config=config,
        task_id=str(args["task_id"]),
        allow_dirty=bool(args.get("allow_dirty", False)),
    )
    return {
        "task_id": outcome.task_id,
        "status": outcome.status,
        "closed": outcome.closed,
        "allow_dirty": outcome.allow_dirty,
        "gates": outcome.gates,
    }


def _list_agents(
    *,
    repo_root: Path,
    config: SisyphusConfig,
    args: dict[str, object],
    list_agents_fn=list_agents,
    **_: object,
) -> dict[str, object]:
    task_id = optional_str(args.get("task_id"))
    stale_after_seconds = int(args.get("stale_after_seconds", 900))
    return {
        "agents": list_agents_fn(
            repo_root=repo_root,
            config=config,
            task_id=task_id,
            stale_after_seconds=stale_after_seconds,
        )
    }


def _daemon_once(
    *,
    repo_root: Path,
    config: SisyphusConfig,
    args: dict[str, object],
    run_daemon_fn=run_daemon,
    **_: object,
) -> dict[str, object]:
    stats = run_daemon_fn(
        repo_root=repo_root,
        config=config,
        once=True,
        poll_interval_seconds=int(args.get("poll_interval_seconds", 1)),
        max_events=int(args["max_events"]) if args.get("max_events") is not None else None,
    )
    return {
        "processed": stats.processed,
        "failed": stats.failed,
        "skipped": stats.skipped,
        "orchestrated": stats.orchestrated,
    }


TOOL_EXECUTORS = MappingProxyType(
    {
        "sisyphus.plan_approve": _plan_approve,
        "sisyphus.plan_request_changes": _plan_request_changes,
        "sisyphus.plan_revise": _plan_revise,
        "sisyphus.spec_freeze": _spec_freeze,
        "sisyphus.spec_validate": _spec_validate,
        "sisyphus.subtasks_generate": _subtasks_generate,
        "sisyphus.record_external_review": _record_external_review,
        "sisyphus.verify_task": _verify_task,
        "sisyphus.close_task": _close_task,
        "sisyphus.list_agents": _list_agents,
        "sisyphus.daemon_once": _daemon_once,
    }
)


def call_workflow_tool(
    *,
    repo_root: Path,
    config: SisyphusConfig,
    tool_name: str,
    args: dict[str, object],
    approve_plan=approve_task_plan,
    request_changes=request_plan_changes,
    revise_plan=revise_task_plan,
    freeze_spec=freeze_task_spec,
    validate_spec_fn=validate_task_spec,
    generate_subtasks_fn=generate_subtasks,
    record_review=record_external_review,
    verify_task=run_verify,
    close_task=run_close,
    list_agents_fn=list_agents,
    run_daemon_fn=run_daemon,
) -> dict[str, object] | None:
    executor = TOOL_EXECUTORS.get(tool_name)
    if executor is None:
        return None
    return executor(
        repo_root=repo_root,
        config=config,
        args=args,
        approve_plan=approve_plan,
        request_changes=request_changes,
        revise_plan=revise_plan,
        freeze_spec=freeze_spec,
        validate_spec_fn=validate_spec_fn,
        generate_subtasks_fn=generate_subtasks_fn,
        record_review=record_review,
        verify_task=verify_task,
        close_task=close_task,
        list_agents_fn=list_agents_fn,
        run_daemon_fn=run_daemon_fn,
    )


__all__ = ["TOOL_EXECUTORS", "call_workflow_tool"]
