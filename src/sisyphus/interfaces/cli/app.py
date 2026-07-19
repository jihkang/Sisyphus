from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from ...config import load_config
from ...discovery import detect_repo_root
from ...composition.evolution_operator import (
    evaluate_evolution_followup_decision,
    request_evolution_followup,
)
from ...composition.evolution_surface import (
    execute_evolution_surface,
    load_evolution_run_artifacts,
)
from ...evolution.presentation import (
    compare_evolution_runs,
    render_evolution_run_compare,
    render_evolution_run_overview,
    render_evolution_run_report,
    render_evolution_run_status,
)
from .handlers import agent as agent_handlers
from .handlers import evolution as evolution_handlers
from .handlers import ingest as ingest_handlers
from .handlers import operations as operations_handlers
from .handlers import planning as planning_handlers
from .handlers import runtime as runtime_handlers
from .handlers import search as search_handlers
from .handlers import status as status_handlers
from .handlers import verification as verification_handlers
from .dispatch import UnknownCliCommandError, dispatch_command
from .parser import build_parser


def _resolve_repo_root(repo_root: str | Path | None) -> Path:
    if repo_root is None:
        return detect_repo_root(Path.cwd())
    return detect_repo_root(Path(repo_root).resolve())


def handle_new(task_type: str, slug: str, repo_root: str | Path | None = None) -> int:
    repo_root = _resolve_repo_root(repo_root)
    config = load_config(repo_root)
    return runtime_handlers.handle_new(repo_root=repo_root, config=config, task_type=task_type, slug=slug)


def handle_verify(task_id: str, repo_root: str | Path | None = None) -> int:
    repo_root = _resolve_repo_root(repo_root)
    config = load_config(repo_root)
    return verification_handlers.handle_verify(repo_root=repo_root, config=config, task_id=task_id)


def handle_close(task_id: str, allow_dirty: bool, repo_root: str | Path | None = None) -> int:
    repo_root = _resolve_repo_root(repo_root)
    config = load_config(repo_root)
    return verification_handlers.handle_close(
        repo_root=repo_root,
        config=config,
        task_id=task_id,
        allow_dirty=allow_dirty,
    )


def handle_observe(task_id: str, as_json: bool, repo_root: str | Path | None = None) -> int:
    repo_root = _resolve_repo_root(repo_root)
    config = load_config(repo_root)
    return operations_handlers.handle_observe(
        repo_root=repo_root,
        config=config,
        task_id=task_id,
        as_json=as_json,
    )


def handle_episode_check(
    task_id: str,
    episode_id: str | None,
    as_json: bool,
    repo_root: str | Path | None = None,
) -> int:
    repo_root = _resolve_repo_root(repo_root)
    config = load_config(repo_root)
    return operations_handlers.handle_episode_check(
        repo_root=repo_root,
        config=config,
        task_id=task_id,
        episode_id=episode_id,
        as_json=as_json,
    )


def handle_eval_loop(
    task_id: str,
    episode_id: str | None,
    max_action_count: int,
    as_json: bool,
    repo_root: str | Path | None = None,
) -> int:
    repo_root = _resolve_repo_root(repo_root)
    config = load_config(repo_root)
    return operations_handlers.handle_eval_loop(
        repo_root=repo_root,
        config=config,
        task_id=task_id,
        episode_id=episode_id,
        max_action_count=max_action_count,
        as_json=as_json,
    )


def handle_eval_test_first(
    task_id: str,
    episode_id: str | None,
    as_json: bool,
    repo_root: str | Path | None = None,
) -> int:
    repo_root = _resolve_repo_root(repo_root)
    config = load_config(repo_root)
    return operations_handlers.handle_eval_test_first(
        repo_root=repo_root,
        config=config,
        task_id=task_id,
        episode_id=episode_id,
        as_json=as_json,
    )


def handle_benchmark_run(
    fixtures_dir: str | None,
    as_json: bool,
    repo_root: str | Path | None = None,
) -> int:
    repo_root = _resolve_repo_root(repo_root)
    return operations_handlers.handle_benchmark_run(
        repo_root=repo_root,
        fixtures_dir=fixtures_dir,
        as_json=as_json,
    )


def handle_local_agent_benchmark(
    fixtures_file: str | None,
    provider: str,
    provider_args: list[str] | None,
    output: str | None,
    as_json: bool,
    repo_root: str | Path | None = None,
) -> int:
    repo_root = _resolve_repo_root(repo_root)
    return operations_handlers.handle_local_agent_benchmark(
        repo_root=repo_root,
        fixtures_file=fixtures_file,
        provider=provider,
        provider_args=provider_args,
        output=output,
        as_json=as_json,
    )


def handle_dataset_export(
    format: str,
    task_id: str | None,
    output: str | None,
    max_action_count: int,
    repo_root: str | Path | None = None,
) -> int:
    repo_root = _resolve_repo_root(repo_root)
    config = load_config(repo_root)
    return operations_handlers.handle_dataset_export(
        repo_root=repo_root,
        config=config,
        format=format,
        task_id=task_id,
        output=output,
        max_action_count=max_action_count,
    )


def handle_plan_approve(
    task_id: str,
    reviewer: str,
    notes: str | None,
    repo_root: str | Path | None = None,
) -> int:
    repo_root = _resolve_repo_root(repo_root)
    config = load_config(repo_root)
    return planning_handlers.handle_plan_approve(
        repo_root=repo_root,
        config=config,
        task_id=task_id,
        reviewer=reviewer,
        notes=notes,
    )


def handle_plan_request_changes(
    task_id: str,
    reviewer: str,
    notes: str | None,
    repo_root: str | Path | None = None,
) -> int:
    repo_root = _resolve_repo_root(repo_root)
    config = load_config(repo_root)
    return planning_handlers.handle_plan_request_changes(
        repo_root=repo_root,
        config=config,
        task_id=task_id,
        reviewer=reviewer,
        notes=notes,
    )


def handle_plan_revise(
    task_id: str,
    author: str,
    notes: str | None,
    repo_root: str | Path | None = None,
) -> int:
    repo_root = _resolve_repo_root(repo_root)
    config = load_config(repo_root)
    return planning_handlers.handle_plan_revise(
        repo_root=repo_root,
        config=config,
        task_id=task_id,
        author=author,
        notes=notes,
    )


def handle_spec_freeze(
    task_id: str,
    reviewer: str,
    notes: str | None,
    repo_root: str | Path | None = None,
) -> int:
    repo_root = _resolve_repo_root(repo_root)
    config = load_config(repo_root)
    return planning_handlers.handle_spec_freeze(
        repo_root=repo_root,
        config=config,
        task_id=task_id,
        reviewer=reviewer,
        notes=notes,
    )


def handle_spec_validate(
    task_id: str,
    as_json: bool,
    repo_root: str | Path | None = None,
) -> int:
    repo_root = _resolve_repo_root(repo_root)
    config = load_config(repo_root)
    return planning_handlers.handle_spec_validate(
        repo_root=repo_root,
        config=config,
        task_id=task_id,
        as_json=as_json,
    )


def handle_subtasks_generate(task_id: str, repo_root: str | Path | None = None) -> int:
    repo_root = _resolve_repo_root(repo_root)
    config = load_config(repo_root)
    return planning_handlers.handle_subtasks_generate(repo_root=repo_root, config=config, task_id=task_id)


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
    return ingest_handlers.handle_ingest_conversation(
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
        no_run=no_run,
    )


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
    return ingest_handlers.handle_ingest_pull_request_merged(
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
        changed_file_json=changed_file_json,
    )


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
    return ingest_handlers.handle_request(
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
        no_run=no_run,
    )


def handle_daemon(
    once: bool,
    poll_interval_seconds: int,
    max_events: int | None,
    repo_root: str | Path | None = None,
) -> int:
    repo_root = _resolve_repo_root(repo_root)
    config = load_config(repo_root)
    return runtime_handlers.handle_daemon(
        repo_root=repo_root,
        config=config,
        once=once,
        poll_interval_seconds=poll_interval_seconds,
        max_events=max_events,
    )


def handle_serve(poll_interval_seconds: int, repo_root: str | Path | None = None) -> int:
    repo_root = _resolve_repo_root(repo_root)
    config = load_config(repo_root)
    return runtime_handlers.handle_serve(repo_root=repo_root, config=config, poll_interval_seconds=poll_interval_seconds)


def handle_discord_bot(
    token: str | None,
    poll_interval_seconds: int,
    channel_ids: list[int] | None,
    repo_root: str | Path | None = None,
) -> int:
    repo_root = _resolve_repo_root(repo_root)
    config = load_config(repo_root)
    return runtime_handlers.handle_discord_bot(
        repo_root=repo_root,
        config=config,
        token=token,
        poll_interval_seconds=poll_interval_seconds,
        channel_ids=channel_ids,
    )


def handle_agents(
    task_id: str | None,
    as_json: bool,
    stale_after_seconds: int,
    repo_root: str | Path | None = None,
) -> int:
    repo_root = _resolve_repo_root(repo_root)
    config = load_config(repo_root)
    return agent_handlers.handle_agents(
        repo_root=repo_root,
        config=config,
        task_id=task_id,
        stale_after_seconds=stale_after_seconds,
        as_json=as_json,
    )


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
    return agent_handlers.handle_agent_start(
        repo_root=repo_root,
        config=config,
        task_id=task_id,
        agent_id=agent_id,
        role=role,
        status=status,
        provider=provider,
        step=step,
        summary=summary,
        owned_paths=owned_paths,
    )


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
    return agent_handlers.handle_agent_update(
        repo_root=repo_root,
        config=config,
        task_id=task_id,
        agent_id=agent_id,
        status=status,
        provider=provider,
        step=step,
        summary=summary,
        owned_paths=owned_paths,
        command=command,
        pid=pid,
        error=error,
    )


def handle_agent_finish(
    task_id: str,
    agent_id: str,
    status: str,
    summary: str | None,
    error: str | None,
    repo_root: str | Path | None = None,
) -> int:
    repo_root = _resolve_repo_root(repo_root)
    config = load_config(repo_root)
    return agent_handlers.handle_agent_finish(
        repo_root=repo_root,
        config=config,
        task_id=task_id,
        agent_id=agent_id,
        status=status,
        summary=summary,
        error=error,
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
    return agent_handlers.handle_agent_run(
        repo_root=repo_root,
        config=config,
        task_id=task_id,
        agent_id=agent_id,
        role=role,
        provider=provider,
        step=step,
        summary=summary,
        owned_paths=owned_paths,
        heartbeat_seconds=heartbeat_seconds,
        command=command,
        stdin_text=stdin_text,
        env=env,
    )


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
    return status_handlers.handle_status(
        repo_root=repo_root,
        config=config,
        as_json=as_json,
        only_open=only_open,
        only_blocked=only_blocked,
        show_agents=show_agents,
        stale_after_seconds=stale_after_seconds,
    )


def handle_index_rebuild(as_json: bool, repo_root: str | Path | None = None) -> int:
    repo_root = _resolve_repo_root(repo_root)
    config = load_config(repo_root)
    return search_handlers.handle_index_rebuild(repo_root=repo_root, config=config, as_json=as_json)


def handle_search(
    query: str,
    limit: int,
    as_json: bool,
    repo_root: str | Path | None = None,
) -> int:
    repo_root = _resolve_repo_root(repo_root)
    return search_handlers.handle_search(repo_root=repo_root, query=query, limit=limit, as_json=as_json)


def handle_context_build(
    query: str,
    limit: int,
    max_excerpt_chars: int,
    as_json: bool,
    repo_root: str | Path | None = None,
) -> int:
    repo_root = _resolve_repo_root(repo_root)
    config = load_config(repo_root)
    return search_handlers.handle_context_build(
        repo_root=repo_root,
        config=config,
        query=query,
        limit=limit,
        max_excerpt_chars=max_excerpt_chars,
        as_json=as_json,
    )


def handle_evolution_run(run_id: str, repo_root: str | Path | None = None) -> int:
    repo_root = _resolve_repo_root(repo_root)
    return evolution_handlers.handle_evolution_run(
        repo_root=repo_root,
        run_id=run_id,
        load_artifacts=load_evolution_run_artifacts,
        render_overview=render_evolution_run_overview,
    )


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
    return evolution_handlers.handle_evolution_execute(
        repo_root=repo_root,
        config=config,
        run_id=run_id,
        target_ids=target_ids,
        task_ids=task_ids,
        max_events=max_events,
        execute_surface=execute_evolution_surface,
    )


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
    return evolution_handlers.handle_evolution_request_followup(
        repo_root=repo_root,
        config=config,
        run_id=run_id,
        candidate_id=candidate_id,
        title=title,
        summary=summary,
        requested_task_type=requested_task_type,
        slug=slug,
        target_ids=target_ids,
        owned_paths=owned_paths,
        review_gates=review_gates,
        verification_obligation_json=verification_obligation_json,
        evidence_summary_json=evidence_summary_json,
        request_followup=request_evolution_followup,
    )


def handle_evolution_decide(
    *,
    task_id: str,
    claim: str | None,
    repo_root: str | Path | None = None,
) -> int:
    repo_root = _resolve_repo_root(repo_root)
    config = load_config(repo_root)
    return evolution_handlers.handle_evolution_decide(
        repo_root=repo_root,
        config=config,
        task_id=task_id,
        claim=claim,
        decide_followup=evaluate_evolution_followup_decision,
    )


def handle_evolution_status(run_id: str, repo_root: str | Path | None = None) -> int:
    repo_root = _resolve_repo_root(repo_root)
    return evolution_handlers.handle_evolution_status(
        repo_root=repo_root,
        run_id=run_id,
        load_artifacts=load_evolution_run_artifacts,
        render_status=render_evolution_run_status,
    )


def handle_evolution_report(run_id: str, repo_root: str | Path | None = None) -> int:
    repo_root = _resolve_repo_root(repo_root)
    return evolution_handlers.handle_evolution_report(
        repo_root=repo_root,
        run_id=run_id,
        load_artifacts=load_evolution_run_artifacts,
        render_report=render_evolution_run_report,
    )


def handle_evolution_compare(
    left_run_id: str,
    right_run_id: str,
    repo_root: str | Path | None = None,
) -> int:
    repo_root = _resolve_repo_root(repo_root)
    return evolution_handlers.handle_evolution_compare(
        repo_root=repo_root,
        left_run_id=left_run_id,
        right_run_id=right_run_id,
        load_artifacts=load_evolution_run_artifacts,
        compare_runs=compare_evolution_runs,
        render_compare=render_evolution_run_compare,
    )


CLI_HANDLERS = {
    "handle_new": handle_new,
    "handle_request": handle_request,
    "handle_verify": handle_verify,
    "handle_close": handle_close,
    "handle_observe": handle_observe,
    "handle_episode_check": handle_episode_check,
    "handle_eval_loop": handle_eval_loop,
    "handle_eval_test_first": handle_eval_test_first,
    "handle_benchmark_run": handle_benchmark_run,
    "handle_local_agent_benchmark": handle_local_agent_benchmark,
    "handle_dataset_export": handle_dataset_export,
    "handle_plan_approve": handle_plan_approve,
    "handle_plan_request_changes": handle_plan_request_changes,
    "handle_plan_revise": handle_plan_revise,
    "handle_spec_freeze": handle_spec_freeze,
    "handle_spec_validate": handle_spec_validate,
    "handle_subtasks_generate": handle_subtasks_generate,
    "handle_agents": handle_agents,
    "handle_agent_start": handle_agent_start,
    "handle_agent_update": handle_agent_update,
    "handle_agent_finish": handle_agent_finish,
    "handle_agent_run": handle_agent_run,
    "handle_ingest_conversation": handle_ingest_conversation,
    "handle_ingest_pull_request_merged": handle_ingest_pull_request_merged,
    "handle_daemon": handle_daemon,
    "handle_serve": handle_serve,
    "handle_discord_bot": handle_discord_bot,
    "handle_index_rebuild": handle_index_rebuild,
    "handle_search": handle_search,
    "handle_context_build": handle_context_build,
    "handle_evolution_execute": handle_evolution_execute,
    "handle_evolution_request_followup": handle_evolution_request_followup,
    "handle_evolution_decide": handle_evolution_decide,
    "handle_evolution_run": handle_evolution_run,
    "handle_evolution_status": handle_evolution_status,
    "handle_evolution_report": handle_evolution_report,
    "handle_evolution_compare": handle_evolution_compare,
    "handle_status": handle_status,
}


def _current_cli_handlers() -> dict[str, object]:
    return {name: globals()[name] for name in CLI_HANDLERS}


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args, extras = parser.parse_known_args(argv)
    if not (args.command == "agent" and getattr(args, "agent_command", None) == "run") and extras:
        parser.error(f"unrecognized arguments: {' '.join(extras)}")
    try:
        return dispatch_command(args, extras, _current_cli_handlers())
    except UnknownCliCommandError:
        parser.error("unknown command")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
