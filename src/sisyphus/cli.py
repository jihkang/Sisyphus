from __future__ import annotations

import argparse
from collections.abc import Sequence
import json
from pathlib import Path
import sys

from .agents import (
    AGENT_STATUSES,
    DEFAULT_STALE_AFTER_SECONDS,
    AgentTrackingError,
    list_agents,
    register_agent,
    update_agent,
)
from .api import queue_conversation, request_task
from .api import queue_pull_request_merged as queue_pull_request_merged_api
from .agent_runtime import run_tracked_agent
from .audit import run_verify
from .closeout import run_close
from .config import load_config
from .creation import TaskCreationError, create_task_workspace
from .daemon import run_daemon
from .discovery import detect_repo_root
from .evolution.handoff import EvolutionEvidenceSummary, EvolutionVerificationObligation
from .evolution.operator import evaluate_evolution_followup_decision, request_evolution_followup
from .evolution.surface import (
    compare_evolution_runs,
    execute_evolution_surface,
    load_evolution_run_artifacts,
    render_evolution_run_compare,
    render_evolution_run_overview,
    render_evolution_run_report,
    render_evolution_run_status,
)
from .planning import (
    approve_task_plan,
    enforce_plan_approved,
    enforce_spec_frozen,
    freeze_task_spec,
    generate_subtasks,
    request_plan_changes,
    revise_task_plan,
)
from .service import (
    extract_conformance_summary,
    format_conformance_summary,
    run_service,
    summarize_subtask_conformance,
)
from .state import list_task_records, load_task_record


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="sisyphus")
    parser.add_argument("--repo", dest="repo_root", help="Target repository root to manage.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    new_parser = subparsers.add_parser("new")
    new_subparsers = new_parser.add_subparsers(dest="task_type", required=True)

    feature_parser = new_subparsers.add_parser("feature")
    feature_parser.add_argument("slug")

    issue_parser = new_subparsers.add_parser("issue")
    issue_parser.add_argument("slug")

    verify_parser = subparsers.add_parser("verify")
    verify_parser.add_argument("task_id")

    close_parser = subparsers.add_parser("close")
    close_parser.add_argument("task_id")
    close_parser.add_argument("--allow-dirty", action="store_true")

    plan_parser = subparsers.add_parser("plan")
    plan_subparsers = plan_parser.add_subparsers(dest="plan_command", required=True)
    plan_approve_parser = plan_subparsers.add_parser("approve")
    plan_approve_parser.add_argument("task_id")
    plan_approve_parser.add_argument("--by", dest="reviewer", default="operator")
    plan_approve_parser.add_argument("--notes")
    plan_changes_parser = plan_subparsers.add_parser("request-changes")
    plan_changes_parser.add_argument("task_id")
    plan_changes_parser.add_argument("--by", dest="reviewer", default="operator")
    plan_changes_parser.add_argument("--notes")
    plan_revise_parser = plan_subparsers.add_parser("revise")
    plan_revise_parser.add_argument("task_id")
    plan_revise_parser.add_argument("--by", dest="author", default="operator")
    plan_revise_parser.add_argument("--notes")

    spec_parser = subparsers.add_parser("spec")
    spec_subparsers = spec_parser.add_subparsers(dest="spec_command", required=True)
    spec_freeze_parser = spec_subparsers.add_parser("freeze")
    spec_freeze_parser.add_argument("task_id")
    spec_freeze_parser.add_argument("--by", dest="reviewer", default="operator")
    spec_freeze_parser.add_argument("--notes")

    subtasks_parser = subparsers.add_parser("subtasks")
    subtasks_subparsers = subtasks_parser.add_subparsers(dest="subtasks_command", required=True)
    subtasks_generate_parser = subtasks_subparsers.add_parser("generate")
    subtasks_generate_parser.add_argument("task_id")

    request_parser = subparsers.add_parser("request")
    _add_conversation_arguments(request_parser)

    ingest_parser = subparsers.add_parser("ingest")
    ingest_subparsers = ingest_parser.add_subparsers(dest="ingest_command", required=True)
    ingest_conversation_parser = ingest_subparsers.add_parser("conversation")
    _add_conversation_arguments(ingest_conversation_parser)
    ingest_pr_merged_parser = ingest_subparsers.add_parser("pr-merged")
    _add_pull_request_merged_arguments(ingest_pr_merged_parser)

    daemon_parser = subparsers.add_parser("daemon")
    daemon_parser.add_argument("--once", action="store_true")
    daemon_parser.add_argument("--poll-interval-seconds", type=int, default=5)
    daemon_parser.add_argument("--max-events", type=int)

    serve_parser = subparsers.add_parser("serve")
    serve_parser.add_argument("--poll-interval-seconds", type=int, default=5)

    discord_parser = subparsers.add_parser("discord-bot")
    discord_parser.add_argument("--token")
    discord_parser.add_argument("--poll-interval-seconds", type=int, default=5)
    discord_parser.add_argument("--channel-id", type=int, action="append", dest="channel_ids")

    status_parser = subparsers.add_parser("status")
    status_parser.add_argument("--json", action="store_true")
    status_parser.add_argument("--open", dest="only_open", action="store_true")
    status_parser.add_argument("--blocked", dest="only_blocked", action="store_true")
    status_parser.add_argument("--agents", action="store_true")
    status_parser.add_argument("--stale-after-seconds", type=int, default=DEFAULT_STALE_AFTER_SECONDS)

    evolution_parser = subparsers.add_parser("evolution")
    evolution_subparsers = evolution_parser.add_subparsers(dest="evolution_command", required=True)
    evolution_execute_parser = evolution_subparsers.add_parser("execute")
    evolution_execute_parser.add_argument("--run-id")
    evolution_execute_parser.add_argument("--target-id", action="append", dest="target_ids")
    evolution_execute_parser.add_argument("--task-id", action="append", dest="task_ids")
    evolution_execute_parser.add_argument("--max-events", type=int, default=50)
    evolution_followup_parser = evolution_subparsers.add_parser("request-followup")
    evolution_followup_parser.add_argument("run_id")
    evolution_followup_parser.add_argument("--candidate-id", required=True)
    evolution_followup_parser.add_argument("--title", required=True)
    evolution_followup_parser.add_argument("--summary", required=True)
    evolution_followup_parser.add_argument(
        "--task-type",
        dest="requested_task_type",
        choices=["feature", "issue"],
        default="feature",
    )
    evolution_followup_parser.add_argument("--slug")
    evolution_followup_parser.add_argument("--target-id", action="append", dest="target_ids")
    evolution_followup_parser.add_argument("--owned-path", action="append", dest="owned_paths")
    evolution_followup_parser.add_argument("--review-gate", action="append", dest="review_gates")
    evolution_followup_parser.add_argument(
        "--verification-obligation-json",
        action="append",
        dest="verification_obligation_json",
    )
    evolution_followup_parser.add_argument(
        "--evidence-summary-json",
        action="append",
        dest="evidence_summary_json",
    )
    evolution_decide_parser = evolution_subparsers.add_parser("decide")
    evolution_decide_parser.add_argument("task_id")
    evolution_decide_parser.add_argument("--claim")
    evolution_run_parser = evolution_subparsers.add_parser("run")
    evolution_run_parser.add_argument("run_id")
    evolution_status_parser = evolution_subparsers.add_parser("status")
    evolution_status_parser.add_argument("run_id")
    evolution_report_parser = evolution_subparsers.add_parser("report")
    evolution_report_parser.add_argument("run_id")
    evolution_compare_parser = evolution_subparsers.add_parser("compare")
    evolution_compare_parser.add_argument("left_run_id")
    evolution_compare_parser.add_argument("right_run_id")

    agents_parser = subparsers.add_parser("agents")
    agents_parser.add_argument("--task-id")
    agents_parser.add_argument("--json", action="store_true")
    agents_parser.add_argument("--stale-after-seconds", type=int, default=DEFAULT_STALE_AFTER_SECONDS)

    agent_parser = subparsers.add_parser("agent")
    agent_subparsers = agent_parser.add_subparsers(dest="agent_command", required=True)

    agent_start_parser = agent_subparsers.add_parser("start")
    agent_start_parser.add_argument("task_id")
    agent_start_parser.add_argument("agent_id")
    agent_start_parser.add_argument("--role", required=True)
    agent_start_parser.add_argument("--status", choices=sorted(AGENT_STATUSES), default="running")
    agent_start_parser.add_argument("--step")
    agent_start_parser.add_argument("--summary")
    agent_start_parser.add_argument("--owned-path", action="append", dest="owned_paths")

    agent_update_parser = agent_subparsers.add_parser("update")
    agent_update_parser.add_argument("task_id")
    agent_update_parser.add_argument("agent_id")
    agent_update_parser.add_argument("--status", choices=sorted(AGENT_STATUSES))
    agent_update_parser.add_argument("--step")
    agent_update_parser.add_argument("--summary")
    agent_update_parser.add_argument("--owned-path", action="append", dest="owned_paths")
    agent_update_parser.add_argument("--error")

    agent_finish_parser = agent_subparsers.add_parser("finish")
    agent_finish_parser.add_argument("task_id")
    agent_finish_parser.add_argument("agent_id")
    agent_finish_parser.add_argument("--status", choices=["completed", "failed", "cancelled"], default="completed")
    agent_finish_parser.add_argument("--summary")
    agent_finish_parser.add_argument("--error")

    agent_run_parser = agent_subparsers.add_parser("run")
    agent_run_parser.add_argument("task_id")
    agent_run_parser.add_argument("agent_id")
    agent_run_parser.add_argument("--role", required=True)
    agent_run_parser.add_argument("--provider", required=True)
    agent_run_parser.add_argument("--step")
    agent_run_parser.add_argument("--summary")
    agent_run_parser.add_argument("--owned-path", action="append", dest="owned_paths")
    agent_run_parser.add_argument("--heartbeat-seconds", type=int, default=10)

    return parser


def _add_conversation_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("message")
    parser.add_argument("--title")
    parser.add_argument("--task-type", choices=["feature", "issue"], default="feature")
    parser.add_argument("--slug")
    parser.add_argument("--instruction")
    parser.add_argument("--agent-id", default="worker-1")
    parser.add_argument("--role", default="worker")
    parser.add_argument("--provider", default="codex")
    parser.add_argument("--owned-path", action="append", dest="owned_paths")
    parser.add_argument("--provider-arg", action="append", dest="provider_args")
    parser.add_argument("--adopt-current-changes", action="store_true")
    parser.add_argument("--adopt-path", action="append", dest="adopt_paths")
    parser.add_argument("--no-run", action="store_true")

def _add_pull_request_merged_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--task-id")
    parser.add_argument("--branch")
    parser.add_argument("--repo-full-name")
    parser.add_argument("--pr-number", type=int, required=True)
    parser.add_argument("--title", required=True)
    parser.add_argument("--url")
    parser.add_argument("--base-branch")
    parser.add_argument("--head-branch")
    parser.add_argument("--head-sha")
    parser.add_argument("--merge-commit-sha")
    parser.add_argument("--merged-at")
    parser.add_argument("--merged-by")
    parser.add_argument("--merge-method")
    parser.add_argument("--additions", type=int)
    parser.add_argument("--deletions", type=int)
    parser.add_argument("--changed-file-json", action="append", dest="changed_file_json")
def _resolve_repo_root(repo_root: str | Path | None) -> Path:
    if repo_root is None:
        return detect_repo_root(Path.cwd())
    return detect_repo_root(Path(repo_root).resolve())


def _project_task_for_status_output(task: dict) -> dict:
    projected = dict(task)
    task_conformance = extract_conformance_summary(task)
    if task_conformance:
        projected["conformance_summary"] = task_conformance

    subtasks = task.get("subtasks")
    if isinstance(subtasks, list):
        projected["subtasks"] = [
            _project_subtask_for_status_output(subtask) if isinstance(subtask, dict) else subtask
            for subtask in subtasks
        ]
    return projected


def _project_subtask_for_status_output(subtask: dict) -> dict:
    projected = dict(subtask)
    subtask_conformance = extract_conformance_summary(subtask)
    if subtask_conformance:
        projected["conformance_summary"] = subtask_conformance
    return projected


def handle_new(task_type: str, slug: str, repo_root: str | Path | None = None) -> int:
    repo_root = _resolve_repo_root(repo_root)
    config = load_config(repo_root)
    try:
        outcome = create_task_workspace(repo_root=repo_root, config=config, task_type=task_type, slug=slug)
    except TaskCreationError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    task = outcome.task
    print(f"created {task['id']}")
    print(f"task_dir: {task['task_dir']}")
    print(f"branch: {task['branch']}")
    print(f"worktree_path: {task['worktree_path']}")
    print(f"plan_status: {task['plan_status']}")
    print(f"spec_status: {task['spec_status']}")
    return 0


def handle_verify(task_id: str, repo_root: str | Path | None = None) -> int:
    repo_root = _resolve_repo_root(repo_root)
    config = load_config(repo_root)
    outcome = run_verify(repo_root=repo_root, config=config, task_id=task_id)
    print(f"verified {outcome.task_id}")
    print(f"status: {outcome.status}")
    print(f"audit_attempts: {outcome.audit_attempts}/{outcome.max_audit_attempts}")
    print(f"verify_file: {outcome.verify_file}")
    if outcome.gates:
        print("gates:")
        for gate in outcome.gates:
            print(f"- {gate['code']}: {gate['message']}")
        return 1
    print("gates: none")
    return 0


def handle_close(task_id: str, allow_dirty: bool, repo_root: str | Path | None = None) -> int:
    repo_root = _resolve_repo_root(repo_root)
    config = load_config(repo_root)
    outcome = run_close(repo_root=repo_root, config=config, task_id=task_id, allow_dirty=allow_dirty)
    print(f"close {outcome.task_id}")
    print(f"status: {outcome.status}")
    print(f"closed: {'yes' if outcome.closed else 'no'}")
    if outcome.gates:
        print("gates:")
        for gate in outcome.gates:
            print(f"- {gate['code']}: {gate['message']}")
        return 1
    print("gates: none")
    return 0


def handle_plan_approve(
    task_id: str,
    reviewer: str,
    notes: str | None,
    repo_root: str | Path | None = None,
) -> int:
    repo_root = _resolve_repo_root(repo_root)
    config = load_config(repo_root)
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
    task_id: str,
    reviewer: str,
    notes: str | None,
    repo_root: str | Path | None = None,
) -> int:
    repo_root = _resolve_repo_root(repo_root)
    config = load_config(repo_root)
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
    task_id: str,
    author: str,
    notes: str | None,
    repo_root: str | Path | None = None,
) -> int:
    repo_root = _resolve_repo_root(repo_root)
    config = load_config(repo_root)
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
    task_id: str,
    reviewer: str,
    notes: str | None,
    repo_root: str | Path | None = None,
) -> int:
    repo_root = _resolve_repo_root(repo_root)
    config = load_config(repo_root)
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


def handle_subtasks_generate(task_id: str, repo_root: str | Path | None = None) -> int:
    repo_root = _resolve_repo_root(repo_root)
    config = load_config(repo_root)
    outcome = generate_subtasks(
        repo_root=repo_root,
        config=config,
        task_id=task_id,
    )
    print(f"subtasks {outcome.task_id}")
    print(f"count: {len(outcome.subtasks)}")
    print(f"workflow_phase: {outcome.workflow_phase}")
    return 0


def handle_ingest_conversation(
    message: str,
    title: str | None,
    task_type: str,
    slug: str | None,
    instruction: str | None,
    agent_id: str,
    role: str,
    provider: str,
    owned_paths: list[str] | None,
    provider_args: list[str] | None,
    adopt_current_changes: bool,
    adopt_paths: list[str] | None,
    no_run: bool,
    repo_root: str | Path | None = None,
) -> int:
    repo_root = _resolve_repo_root(repo_root)
    try:
        queued = queue_conversation(
            repo_root=repo_root,
            message=message,
            title=title,
            task_type=task_type,
            slug=slug,
            instruction=instruction,
            agent_id=agent_id,
            role=role,
            provider=provider,
            owned_paths=owned_paths,
            provider_args=provider_args,
            adopt_current_changes=adopt_current_changes,
            adopt_paths=adopt_paths,
            auto_run=not no_run,
        )
    except RuntimeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    print(f"queued {queued.event_id}")
    print(f"event_file: {queued.event_path}")
    print(f"task_type: {queued.event['payload']['task_type']}")
    print(f"slug: {queued.event['payload']['slug']}")
    return 0

def handle_ingest_pull_request_merged(
    *,
    task_id: str | None,
    branch: str | None,
    repo_full_name: str | None,
    pr_number: int,
    title: str,
    url: str | None,
    base_branch: str | None,
    head_branch: str | None,
    head_sha: str | None,
    merge_commit_sha: str | None,
    merged_at: str | None,
    merged_by: str | None,
    merge_method: str | None,
    additions: int | None,
    deletions: int | None,
    changed_file_json: list[str] | None,
    repo_root: str | Path | None = None,
) -> int:
    repo_root = _resolve_repo_root(repo_root)
    try:
        queued = queue_pull_request_merged_api(
            repo_root=repo_root,
            task_id=task_id,
            branch=branch,
            repo_full_name=repo_full_name,
            pr_number=pr_number,
            title=title,
            url=url,
            base_branch=base_branch,
            head_branch=head_branch,
            head_sha=head_sha,
            merge_commit_sha=merge_commit_sha,
            merged_at=merged_at,
            merged_by=merged_by,
            merge_method=merge_method,
            additions=additions,
            deletions=deletions,
            changed_files=_parse_changed_file_json(changed_file_json),
        )
    except (RuntimeError, ValueError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    print(f"queued {queued.event_id}")
    print(f"event_file: {queued.event_path}")
    print(f"pr_number: {queued.event['payload']['pr_number']}")
    if queued.event["payload"].get("task_id"):
        print(f"task_id: {queued.event['payload']['task_id']}")
    if queued.event["payload"].get("branch"):
        print(f"branch: {queued.event['payload']['branch']}")
    return 0
def handle_request(
    message: str,
    title: str | None,
    task_type: str,
    slug: str | None,
    instruction: str | None,
    agent_id: str,
    role: str,
    provider: str,
    owned_paths: list[str] | None,
    provider_args: list[str] | None,
    adopt_current_changes: bool,
    adopt_paths: list[str] | None,
    no_run: bool,
    repo_root: str | Path | None = None,
) -> int:
    repo_root = _resolve_repo_root(repo_root)
    result = request_task(
        repo_root=repo_root,
        message=message,
        title=title,
        task_type=task_type,
        slug=slug,
        instruction=instruction,
        agent_id=agent_id,
        role=role,
        provider=provider,
        owned_paths=owned_paths,
        provider_args=provider_args,
        adopt_current_changes=adopt_current_changes,
        adopt_paths=adopt_paths,
        auto_run=not no_run,
    )
    if not result.ok:
        print(f"error: {result.error or 'request processing failed'}", file=sys.stderr)
        return 1

    if not result.task_id or not result.task:
        print(f"error: request completed without task id for event {result.event_id}", file=sys.stderr)
        return 1
    task = result.task

    print(f"request {result.event_id}")
    print(f"task_id: {task['id']}")
    print(f"slug: {task.get('slug')}")
    requested_slug = task.get("meta", {}).get("requested_slug")
    if requested_slug and requested_slug != task.get("slug"):
        print(f"requested_slug: {requested_slug}")
    followup_of_task_id = task.get("meta", {}).get("followup_of_task_id")
    if followup_of_task_id:
        print(f"followup_of_task_id: {followup_of_task_id}")
    print(f"status: {task.get('status')}")
    print(f"plan_status: {task.get('plan_status')}")
    print(f"spec_status: {task.get('spec_status')}")
    print(f"workflow_phase: {task.get('workflow_phase')}")
    adopted = task.get("meta", {}).get("adopted_changes")
    if isinstance(adopted, dict) and adopted.get("paths"):
        print(f"adopted_paths: {len(adopted['paths'])}")
        if adopted.get("source_branch"):
            print(f"adopted_from_branch: {adopted['source_branch']}")
    print(f"orchestrated: {result.orchestrated}")
    return 0

def _parse_changed_file_json(entries: list[str] | None) -> list[dict[str, object]] | None:
    if not entries:
        return None
    parsed: list[dict[str, object]] = []
    for entry in entries:
        value = json.loads(entry)
        if not isinstance(value, dict):
            raise ValueError("each --changed-file-json entry must decode to an object")
        parsed.append({str(key): value[key] for key in value})
    return parsed


def _parse_verification_obligation_json(
    entries: list[str] | None,
) -> tuple[EvolutionVerificationObligation, ...] | None:
    if entries is None:
        return None
    obligations: list[EvolutionVerificationObligation] = []
    for index, entry in enumerate(entries, start=1):
        value = json.loads(entry)
        if not isinstance(value, dict):
            raise ValueError(f"verification obligation entry {index} must decode to an object")
        claim = str(value.get("claim", "")).strip()
        method = str(value.get("method", "")).strip()
        if not claim or not method:
            raise ValueError(
                f"verification obligation entry {index} requires non-empty `claim` and `method`"
            )
        obligations.append(
            EvolutionVerificationObligation(
                claim=claim,
                method=method,
                required=bool(value.get("required", True)),
            )
        )
    return tuple(obligations)


def _parse_evidence_summary_json(
    entries: list[str] | None,
) -> tuple[EvolutionEvidenceSummary, ...] | None:
    if entries is None:
        return None
    evidence: list[EvolutionEvidenceSummary] = []
    for index, entry in enumerate(entries, start=1):
        value = json.loads(entry)
        if not isinstance(value, dict):
            raise ValueError(f"evidence summary entry {index} must decode to an object")
        kind = str(value.get("kind", "")).strip()
        summary = str(value.get("summary", "")).strip()
        if not kind or not summary:
            raise ValueError(
                f"evidence summary entry {index} requires non-empty `kind` and `summary`"
            )
        locator = value.get("locator")
        evidence.append(
            EvolutionEvidenceSummary(
                kind=kind,
                summary=summary,
                locator=str(locator).strip() if locator not in (None, "") else None,
            )
        )
    return tuple(evidence)


def handle_daemon(
    once: bool,
    poll_interval_seconds: int,
    max_events: int | None,
    repo_root: str | Path | None = None,
) -> int:
    repo_root = _resolve_repo_root(repo_root)
    config = load_config(repo_root)
    stats = run_daemon(
        repo_root=repo_root,
        config=config,
        once=once,
        poll_interval_seconds=poll_interval_seconds,
        max_events=max_events,
    )
    print(f"processed: {stats.processed}")
    print(f"failed: {stats.failed}")
    print(f"skipped: {stats.skipped}")
    print(f"orchestrated: {stats.orchestrated}")
    return 0 if stats.failed == 0 else 1


def handle_serve(poll_interval_seconds: int, repo_root: str | Path | None = None) -> int:
    repo_root = _resolve_repo_root(repo_root)
    config = load_config(repo_root)
    run_service(
        repo_root=repo_root,
        config=config,
        poll_interval_seconds=poll_interval_seconds,
    )
    return 0


def handle_discord_bot(
    token: str | None,
    poll_interval_seconds: int,
    channel_ids: list[int] | None,
    repo_root: str | Path | None = None,
) -> int:
    from .discord_bot import run_discord_bot

    repo_root = _resolve_repo_root(repo_root)
    config = load_config(repo_root)
    try:
        return run_discord_bot(
            repo_root=repo_root,
            config=config,
            token=token,
            poll_interval_seconds=poll_interval_seconds,
            allowed_channel_ids=channel_ids,
        )
    except RuntimeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


def handle_agents(
    task_id: str | None,
    as_json: bool,
    stale_after_seconds: int,
    repo_root: str | Path | None = None,
) -> int:
    repo_root = _resolve_repo_root(repo_root)
    config = load_config(repo_root)
    agents = list_agents(
        repo_root=repo_root,
        config=config,
        task_id=task_id,
        stale_after_seconds=stale_after_seconds,
    )

    if as_json:
        print(json.dumps(agents, indent=2))
        return 0

    if not agents:
        print("no agents found")
        return 0

    for agent in agents:
        print(
            f"{agent.get('agent_id')} "
            f"task={agent.get('parent_task_id')} "
            f"provider={agent.get('provider') or 'n/a'} "
            f"role={agent.get('role')} "
            f"status={agent.get('status')}"
        )
        if agent.get("pid") is not None:
            print(f"  pid: {agent['pid']}")
        if agent.get("current_step"):
            print(f"  step: {agent['current_step']}")
        if agent.get("last_message_summary"):
            print(f"  summary: {agent['last_message_summary']}")
        if agent.get("owned_paths"):
            print(f"  owned_paths: {', '.join(agent['owned_paths'])}")
        if agent.get("command"):
            print(f"  command: {' '.join(agent['command'])}")
        if agent.get("error"):
            print(f"  error: {agent['error']}")
    return 0


def handle_agent_start(
    task_id: str,
    agent_id: str,
    role: str,
    status: str,
    provider: str | None,
    step: str | None,
    summary: str | None,
    owned_paths: list[str] | None,
    repo_root: str | Path | None = None,
) -> int:
    repo_root = _resolve_repo_root(repo_root)
    config = load_config(repo_root)
    try:
        agent = register_agent(
            repo_root=repo_root,
            config=config,
            task_id=task_id,
            agent_id=agent_id,
            role=role,
            provider=provider,
            current_step=step,
            last_message_summary=summary,
            owned_paths=owned_paths,
            status=status,
        )
    except (AgentTrackingError, FileNotFoundError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    print(f"agent {agent['agent_id']}")
    print(f"task: {agent['parent_task_id']}")
    print(f"status: {agent['status']}")
    return 0


def handle_agent_update(
    task_id: str,
    agent_id: str,
    status: str | None,
    provider: str | None,
    step: str | None,
    summary: str | None,
    owned_paths: list[str] | None,
    command: list[str] | None,
    pid: int | None,
    error: str | None,
    repo_root: str | Path | None = None,
) -> int:
    repo_root = _resolve_repo_root(repo_root)
    config = load_config(repo_root)
    try:
        agent = update_agent(
            repo_root=repo_root,
            config=config,
            task_id=task_id,
            agent_id=agent_id,
            status=status,
            provider=provider,
            current_step=step,
            last_message_summary=summary,
            owned_paths=owned_paths,
            command=command,
            pid=pid,
            error=error,
        )
    except (AgentTrackingError, FileNotFoundError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    print(f"agent {agent['agent_id']}")
    print(f"task: {agent['parent_task_id']}")
    print(f"status: {agent['status']}")
    return 0


def handle_agent_finish(
    task_id: str,
    agent_id: str,
    status: str,
    summary: str | None,
    error: str | None,
    repo_root: str | Path | None = None,
) -> int:
    return handle_agent_update(
        task_id=task_id,
        agent_id=agent_id,
        status=status,
        provider=None,
        step=None,
        summary=summary,
        owned_paths=None,
        command=None,
        pid=None,
        error=error,
        repo_root=repo_root,
    )


def handle_agent_run(
    task_id: str,
    agent_id: str,
    role: str,
    provider: str,
    step: str | None,
    summary: str | None,
    owned_paths: list[str] | None,
    heartbeat_seconds: int,
    command: list[str],
    stdin_text: str | None = None,
    env: dict[str, str] | None = None,
    repo_root: str | Path | None = None,
) -> int:
    repo_root = _resolve_repo_root(repo_root)
    config = load_config(repo_root)
    if command and command[0] == "--":
        command = command[1:]
    if role == "worker":
        approved, task = enforce_plan_approved(
            repo_root=repo_root,
            config=config,
            task_id=task_id,
            action="execution",
        )
        if not approved:
            plan_gates = [gate for gate in task.get("gates", []) if gate.get("source") == "plan"]
            message = plan_gates[0]["message"] if plan_gates else "task plan approval required before execution"
            print(f"error: {message}", file=sys.stderr)
            return 1
        frozen, task = enforce_spec_frozen(
            repo_root=repo_root,
            config=config,
            task_id=task_id,
            action="execution",
        )
        if not frozen:
            spec_gates = [gate for gate in task.get("gates", []) if gate.get("source") == "spec"]
            message = spec_gates[0]["message"] if spec_gates else "task spec must be frozen before execution"
            print(f"error: {message}", file=sys.stderr)
            return 1
    try:
        outcome = run_tracked_agent(
            repo_root=repo_root,
            config=config,
            task_id=task_id,
            agent_id=agent_id,
            role=role,
            provider=provider,
            command=command,
            current_step=step,
            last_message_summary=summary,
            owned_paths=owned_paths,
            heartbeat_seconds=heartbeat_seconds,
            run_cwd=repo_root,
            stdin_text=stdin_text,
            env=env,
        )
    except (AgentTrackingError, FileNotFoundError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    print(f"agent {outcome.agent_id}")
    print(f"task: {outcome.task_id}")
    print(f"status: {outcome.status}")
    print(f"exit_code: {outcome.exit_code}")
    return outcome.exit_code


def handle_status(
    as_json: bool,
    only_open: bool,
    only_blocked: bool,
    show_agents: bool,
    stale_after_seconds: int,
    repo_root: str | Path | None = None,
) -> int:
    repo_root = _resolve_repo_root(repo_root)
    config = load_config(repo_root)
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
        tasks = [_project_task_for_status_output(task) for task in tasks]
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


def handle_evolution_run(run_id: str, repo_root: str | Path | None = None) -> int:
    repo_root = _resolve_repo_root(repo_root)
    try:
        artifacts = load_evolution_run_artifacts(repo_root, run_id)
    except (FileNotFoundError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(render_evolution_run_overview(artifacts), end="")
    return 0


def handle_evolution_execute(
    *,
    run_id: str | None,
    target_ids: Sequence[str] | None,
    task_ids: Sequence[str] | None,
    max_events: int,
    repo_root: str | Path | None = None,
) -> int:
    repo_root = _resolve_repo_root(repo_root)
    config = load_config(repo_root)
    result = execute_evolution_surface(
        repo_root,
        run_id=run_id,
        target_ids=target_ids,
        task_ids=task_ids,
        max_events=max_events,
        config=config,
    )
    if result.ok:
        print(result.content, end="" if result.content.endswith("\n") else "\n")
        return 0
    print(f"error: {result.error or 'evolution execute failed'}", file=sys.stderr)
    if result.run_id:
        print(f"run_id: {result.run_id}", file=sys.stderr)
    if result.artifact_dir:
        print(f"artifact_dir: {result.artifact_dir}", file=sys.stderr)
    if result.failure_stage:
        print(f"failure_stage: {result.failure_stage}", file=sys.stderr)
    if result.error_type:
        print(f"error_type: {result.error_type}", file=sys.stderr)
    return 1


def handle_evolution_request_followup(
    *,
    run_id: str,
    candidate_id: str,
    title: str,
    summary: str,
    requested_task_type: str,
    slug: str | None,
    target_ids: Sequence[str] | None,
    owned_paths: Sequence[str] | None,
    review_gates: Sequence[str] | None,
    verification_obligation_json: list[str] | None,
    evidence_summary_json: list[str] | None,
    repo_root: str | Path | None = None,
) -> int:
    repo_root = _resolve_repo_root(repo_root)
    config = load_config(repo_root)
    try:
        result = request_evolution_followup(
            repo_root,
            run_id=run_id,
            candidate_id=candidate_id,
            title=title,
            summary=summary,
            requested_task_type=requested_task_type,
            slug=slug,
            target_ids=target_ids,
            owned_paths=owned_paths,
            review_gates=review_gates,
            verification_obligations=_parse_verification_obligation_json(verification_obligation_json),
            evidence_summary=_parse_evidence_summary_json(evidence_summary_json),
            config=config,
        )
    except (FileNotFoundError, RuntimeError, TypeError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(result.content, end="" if result.content.endswith("\n") else "\n")
    return 0


def handle_evolution_decide(
    *,
    task_id: str,
    claim: str | None,
    repo_root: str | Path | None = None,
) -> int:
    repo_root = _resolve_repo_root(repo_root)
    config = load_config(repo_root)
    try:
        result = evaluate_evolution_followup_decision(
            repo_root,
            task_id=task_id,
            claim=claim,
            config=config,
        )
    except (FileNotFoundError, RuntimeError, TypeError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(result.content, end="" if result.content.endswith("\n") else "\n")
    return 0


def handle_evolution_status(run_id: str, repo_root: str | Path | None = None) -> int:
    repo_root = _resolve_repo_root(repo_root)
    try:
        artifacts = load_evolution_run_artifacts(repo_root, run_id)
    except (FileNotFoundError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(render_evolution_run_status(artifacts), end="")
    return 0


def handle_evolution_report(run_id: str, repo_root: str | Path | None = None) -> int:
    repo_root = _resolve_repo_root(repo_root)
    try:
        artifacts = load_evolution_run_artifacts(repo_root, run_id)
    except (FileNotFoundError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(render_evolution_run_report(artifacts), end="")
    return 0


def handle_evolution_compare(
    left_run_id: str,
    right_run_id: str,
    repo_root: str | Path | None = None,
) -> int:
    repo_root = _resolve_repo_root(repo_root)
    try:
        left = load_evolution_run_artifacts(repo_root, left_run_id)
        right = load_evolution_run_artifacts(repo_root, right_run_id)
    except (FileNotFoundError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    comparison = compare_evolution_runs(left, right)
    print(render_evolution_run_compare(comparison), end="")
    return 0


def main() -> int:
    parser = build_parser()
    args, extras = parser.parse_known_args()
    if not (args.command == "agent" and getattr(args, "agent_command", None) == "run") and extras:
        parser.error(f"unrecognized arguments: {' '.join(extras)}")

    if args.command == "new":
        return handle_new(task_type=args.task_type, slug=args.slug, repo_root=args.repo_root)
    if args.command == "request":
        return handle_request(
            message=args.message,
            title=args.title,
            task_type=args.task_type,
            slug=args.slug,
            instruction=args.instruction,
            agent_id=args.agent_id,
            role=args.role,
            provider=args.provider,
            owned_paths=args.owned_paths,
            provider_args=args.provider_args,
            adopt_current_changes=args.adopt_current_changes,
            adopt_paths=args.adopt_paths,
            no_run=args.no_run,
            repo_root=args.repo_root,
        )
    if args.command == "verify":
        return handle_verify(task_id=args.task_id, repo_root=args.repo_root)
    if args.command == "close":
        return handle_close(task_id=args.task_id, allow_dirty=args.allow_dirty, repo_root=args.repo_root)
    if args.command == "plan":
        if args.plan_command == "approve":
            return handle_plan_approve(
                task_id=args.task_id,
                reviewer=args.reviewer,
                notes=args.notes,
                repo_root=args.repo_root,
            )
        if args.plan_command == "request-changes":
            return handle_plan_request_changes(
                task_id=args.task_id,
                reviewer=args.reviewer,
                notes=args.notes,
                repo_root=args.repo_root,
            )
        if args.plan_command == "revise":
            return handle_plan_revise(
                task_id=args.task_id,
                author=args.author,
                notes=args.notes,
                repo_root=args.repo_root,
            )
    if args.command == "spec":
        if args.spec_command == "freeze":
            return handle_spec_freeze(
                task_id=args.task_id,
                reviewer=args.reviewer,
                notes=args.notes,
                repo_root=args.repo_root,
            )
    if args.command == "subtasks":
        if args.subtasks_command == "generate":
            return handle_subtasks_generate(task_id=args.task_id, repo_root=args.repo_root)
    if args.command == "agents":
        return handle_agents(
            task_id=args.task_id,
            as_json=args.json,
            stale_after_seconds=args.stale_after_seconds,
            repo_root=args.repo_root,
        )
    if args.command == "agent":
        if args.agent_command == "start":
            return handle_agent_start(
                task_id=args.task_id,
                agent_id=args.agent_id,
                role=args.role,
                status=args.status,
                provider=None,
                step=args.step,
                summary=args.summary,
                owned_paths=args.owned_paths,
                repo_root=args.repo_root,
            )
        if args.agent_command == "update":
            return handle_agent_update(
                task_id=args.task_id,
                agent_id=args.agent_id,
                status=args.status,
                provider=None,
                step=args.step,
                summary=args.summary,
                owned_paths=args.owned_paths,
                command=None,
                pid=None,
                error=args.error,
                repo_root=args.repo_root,
            )
        if args.agent_command == "finish":
            return handle_agent_finish(
                task_id=args.task_id,
                agent_id=args.agent_id,
                status=args.status,
                summary=args.summary,
                error=args.error,
                repo_root=args.repo_root,
            )
        if args.agent_command == "run":
            return handle_agent_run(
                task_id=args.task_id,
                agent_id=args.agent_id,
                role=args.role,
                provider=args.provider,
                step=args.step,
                summary=args.summary,
                owned_paths=args.owned_paths,
                heartbeat_seconds=args.heartbeat_seconds,
                command=extras,
                repo_root=args.repo_root,
            )
    if args.command == "ingest":
        if args.ingest_command == "conversation":
            return handle_ingest_conversation(
                message=args.message,
                title=args.title,
                task_type=args.task_type,
                slug=args.slug,
                instruction=args.instruction,
                agent_id=args.agent_id,
                role=args.role,
                provider=args.provider,
                owned_paths=args.owned_paths,
                provider_args=args.provider_args,
                adopt_current_changes=args.adopt_current_changes,
                adopt_paths=args.adopt_paths,
                no_run=args.no_run,
                repo_root=args.repo_root,
            )
        if args.ingest_command == "pr-merged":
            return handle_ingest_pull_request_merged(
                task_id=args.task_id,
                branch=args.branch,
                repo_full_name=args.repo_full_name,
                pr_number=args.pr_number,
                title=args.title,
                url=args.url,
                base_branch=args.base_branch,
                head_branch=args.head_branch,
                head_sha=args.head_sha,
                merge_commit_sha=args.merge_commit_sha,
                merged_at=args.merged_at,
                merged_by=args.merged_by,
                merge_method=args.merge_method,
                additions=args.additions,
                deletions=args.deletions,
                changed_file_json=args.changed_file_json,
                repo_root=args.repo_root,
            )
    if args.command == "daemon":
        return handle_daemon(
            once=args.once,
            poll_interval_seconds=args.poll_interval_seconds,
            max_events=args.max_events,
            repo_root=args.repo_root,
        )
    if args.command == "serve":
        return handle_serve(
            poll_interval_seconds=args.poll_interval_seconds,
            repo_root=args.repo_root,
        )
    if args.command == "discord-bot":
        return handle_discord_bot(
            token=args.token,
            poll_interval_seconds=args.poll_interval_seconds,
            channel_ids=args.channel_ids,
            repo_root=args.repo_root,
        )
    if args.command == "evolution":
        if args.evolution_command == "execute":
            return handle_evolution_execute(
                run_id=args.run_id,
                target_ids=args.target_ids,
                task_ids=args.task_ids,
                max_events=args.max_events,
                repo_root=args.repo_root,
            )
        if args.evolution_command == "request-followup":
            return handle_evolution_request_followup(
                run_id=args.run_id,
                candidate_id=args.candidate_id,
                title=args.title,
                summary=args.summary,
                requested_task_type=args.requested_task_type,
                slug=args.slug,
                target_ids=args.target_ids,
                owned_paths=args.owned_paths,
                review_gates=args.review_gates,
                verification_obligation_json=args.verification_obligation_json,
                evidence_summary_json=args.evidence_summary_json,
                repo_root=args.repo_root,
            )
        if args.evolution_command == "decide":
            return handle_evolution_decide(
                task_id=args.task_id,
                claim=args.claim,
                repo_root=args.repo_root,
            )
        if args.evolution_command == "run":
            return handle_evolution_run(run_id=args.run_id, repo_root=args.repo_root)
        if args.evolution_command == "status":
            return handle_evolution_status(run_id=args.run_id, repo_root=args.repo_root)
        if args.evolution_command == "report":
            return handle_evolution_report(run_id=args.run_id, repo_root=args.repo_root)
        if args.evolution_command == "compare":
            return handle_evolution_compare(
                left_run_id=args.left_run_id,
                right_run_id=args.right_run_id,
                repo_root=args.repo_root,
            )
    if args.command == "status":
        return handle_status(
            as_json=args.json,
            only_open=args.only_open,
            only_blocked=args.only_blocked,
            show_agents=args.agents,
            stale_after_seconds=args.stale_after_seconds,
            repo_root=args.repo_root,
        )

    parser.error("unknown command")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
