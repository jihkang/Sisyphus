from __future__ import annotations

import argparse

from ...domain.agent import AGENT_STATUSES, DEFAULT_STALE_AFTER_SECONDS
from ...dataset_export import DATASET_FORMATS
from ...providers.local_openai import LOCAL_OPENAI_PROVIDERS


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

    review_parser = subparsers.add_parser("review")
    review_subparsers = review_parser.add_subparsers(dest="review_command", required=True)
    review_scope_parser = review_subparsers.add_parser("scope")
    review_scope_parser.add_argument("task_id")
    review_scope_parser.add_argument("--json", action="store_true")
    review_record_parser = review_subparsers.add_parser("record")
    review_record_parser.add_argument("task_id")
    review_record_parser.add_argument("--envelope", dest="envelope_path", required=True)
    review_record_parser.add_argument("--json", action="store_true")

    close_parser = subparsers.add_parser("close")
    close_parser.add_argument("task_id")
    close_parser.add_argument("--allow-dirty", action="store_true")

    observe_parser = subparsers.add_parser("observe")
    observe_parser.add_argument("task_id")
    observe_parser.add_argument("--json", action="store_true")

    episode_parser = subparsers.add_parser("episode")
    episode_subparsers = episode_parser.add_subparsers(dest="episode_command", required=True)
    episode_check_parser = episode_subparsers.add_parser("check")
    episode_check_parser.add_argument("task_id")
    episode_check_parser.add_argument("--episode-id")
    episode_check_parser.add_argument("--json", action="store_true")

    eval_parser = subparsers.add_parser("eval")
    eval_subparsers = eval_parser.add_subparsers(dest="eval_command", required=True)
    eval_loop_parser = eval_subparsers.add_parser("loop")
    eval_loop_parser.add_argument("task_id")
    eval_loop_parser.add_argument("--episode-id")
    eval_loop_parser.add_argument("--max-action-count", type=int, default=50)
    eval_loop_parser.add_argument("--json", action="store_true")
    eval_test_first_parser = eval_subparsers.add_parser("test-first")
    eval_test_first_parser.add_argument("task_id")
    eval_test_first_parser.add_argument("--episode-id")
    eval_test_first_parser.add_argument("--json", action="store_true")

    benchmark_parser = subparsers.add_parser("benchmark")
    benchmark_subparsers = benchmark_parser.add_subparsers(dest="benchmark_command", required=True)
    benchmark_run_parser = benchmark_subparsers.add_parser("run")
    benchmark_run_parser.add_argument("--fixtures-dir")
    benchmark_run_parser.add_argument("--json", action="store_true")
    local_agent_benchmark_parser = benchmark_subparsers.add_parser("local-agent")
    local_agent_benchmark_parser.add_argument("--fixtures-file")
    local_agent_benchmark_parser.add_argument(
        "--provider",
        choices=sorted(LOCAL_OPENAI_PROVIDERS),
        default="gemma",
    )
    local_agent_benchmark_parser.add_argument(
        "--provider-arg",
        action="append",
        dest="provider_args",
    )
    local_agent_benchmark_parser.add_argument("--output")
    local_agent_benchmark_parser.add_argument("--json", action="store_true")

    dataset_parser = subparsers.add_parser("dataset")
    dataset_subparsers = dataset_parser.add_subparsers(dest="dataset_command", required=True)
    dataset_export_parser = dataset_subparsers.add_parser("export")
    dataset_export_parser.add_argument("--format", choices=DATASET_FORMATS, required=True)
    dataset_export_parser.add_argument("--task-id")
    dataset_export_parser.add_argument("--output")
    dataset_export_parser.add_argument("--max-action-count", type=int, default=50)

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
    spec_validate_parser = spec_subparsers.add_parser("validate")
    spec_validate_parser.add_argument("task_id")
    spec_validate_parser.add_argument("--json", action="store_true")

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

    index_parser = subparsers.add_parser("index")
    index_subparsers = index_parser.add_subparsers(dest="index_command", required=True)
    index_rebuild_parser = index_subparsers.add_parser("rebuild")
    index_rebuild_parser.add_argument("--json", action="store_true")

    search_parser = subparsers.add_parser("search")
    search_parser.add_argument("query")
    search_parser.add_argument("--limit", type=int, default=10)
    search_parser.add_argument("--json", action="store_true")

    context_parser = subparsers.add_parser("context")
    context_subparsers = context_parser.add_subparsers(dest="context_command", required=True)
    context_build_parser = context_subparsers.add_parser("build")
    context_build_parser.add_argument("query")
    context_build_parser.add_argument("--limit", type=int, default=5)
    context_build_parser.add_argument("--max-excerpt-chars", type=int, default=800)
    context_build_parser.add_argument("--json", action="store_true")

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


__all__ = [
    "build_parser",
]
