from __future__ import annotations

from argparse import Namespace
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any


class UnknownCliCommandError(ValueError):
    pass


ArgumentBinding = str | tuple[str, str]


@dataclass(frozen=True, slots=True)
class CliCommandSpec:
    path: tuple[str, ...]
    handler_name: str
    argument_names: tuple[ArgumentBinding, ...] = ()
    extra_argument_name: str | None = None
    constant_kwargs: Mapping[str, object] = field(default_factory=dict)


CliHandler = Callable[..., int]


COMMAND_SPECS: tuple[CliCommandSpec, ...] = (
    CliCommandSpec(("new",), "handle_new", ("task_type", "slug")),
    CliCommandSpec(
        ("request",),
        "handle_request",
        (
            "message",
            "title",
            "task_type",
            "slug",
            "instruction",
            "agent_id",
            "role",
            "provider",
            "owned_paths",
            "provider_args",
            "adopt_current_changes",
            "adopt_paths",
            "no_run",
        ),
    ),
    CliCommandSpec(("verify",), "handle_verify", ("task_id",)),
    CliCommandSpec(("close",), "handle_close", ("task_id", "allow_dirty")),
    CliCommandSpec(("observe",), "handle_observe", ("task_id", ("json", "as_json"))),
    CliCommandSpec(("episode", "check"), "handle_episode_check", ("task_id", "episode_id", ("json", "as_json"))),
    CliCommandSpec(
        ("eval", "loop"),
        "handle_eval_loop",
        ("task_id", "episode_id", "max_action_count", ("json", "as_json")),
    ),
    CliCommandSpec(("eval", "test-first"), "handle_eval_test_first", ("task_id", "episode_id", ("json", "as_json"))),
    CliCommandSpec(("benchmark", "run"), "handle_benchmark_run", ("fixtures_dir", ("json", "as_json"))),
    CliCommandSpec(("dataset", "export"), "handle_dataset_export", ("format", "task_id", "output", "max_action_count")),
    CliCommandSpec(("plan", "approve"), "handle_plan_approve", ("task_id", "reviewer", "notes")),
    CliCommandSpec(("plan", "request-changes"), "handle_plan_request_changes", ("task_id", "reviewer", "notes")),
    CliCommandSpec(("plan", "revise"), "handle_plan_revise", ("task_id", "author", "notes")),
    CliCommandSpec(("spec", "freeze"), "handle_spec_freeze", ("task_id", "reviewer", "notes")),
    CliCommandSpec(("subtasks", "generate"), "handle_subtasks_generate", ("task_id",)),
    CliCommandSpec(("agents",), "handle_agents", ("task_id", ("json", "as_json"), "stale_after_seconds")),
    CliCommandSpec(
        ("agent", "start"),
        "handle_agent_start",
        ("task_id", "agent_id", "role", "status", "step", "summary", "owned_paths"),
        constant_kwargs={"provider": None},
    ),
    CliCommandSpec(
        ("agent", "update"),
        "handle_agent_update",
        ("task_id", "agent_id", "status", "step", "summary", "owned_paths", "error"),
        constant_kwargs={"provider": None, "command": None, "pid": None},
    ),
    CliCommandSpec(("agent", "finish"), "handle_agent_finish", ("task_id", "agent_id", "status", "summary", "error")),
    CliCommandSpec(
        ("agent", "run"),
        "handle_agent_run",
        ("task_id", "agent_id", "role", "provider", "step", "summary", "owned_paths", "heartbeat_seconds"),
        extra_argument_name="command",
    ),
    CliCommandSpec(
        ("ingest", "conversation"),
        "handle_ingest_conversation",
        (
            "message",
            "title",
            "task_type",
            "slug",
            "instruction",
            "agent_id",
            "role",
            "provider",
            "owned_paths",
            "provider_args",
            "adopt_current_changes",
            "adopt_paths",
            "no_run",
        ),
    ),
    CliCommandSpec(
        ("ingest", "pr-merged"),
        "handle_ingest_pull_request_merged",
        (
            "task_id",
            "branch",
            "repo_full_name",
            "pr_number",
            "title",
            "url",
            "base_branch",
            "head_branch",
            "head_sha",
            "merge_commit_sha",
            "merged_at",
            "merged_by",
            "merge_method",
            "additions",
            "deletions",
            "changed_file_json",
        ),
    ),
    CliCommandSpec(("daemon",), "handle_daemon", ("once", "poll_interval_seconds", "max_events")),
    CliCommandSpec(("serve",), "handle_serve", ("poll_interval_seconds",)),
    CliCommandSpec(("discord-bot",), "handle_discord_bot", ("token", "poll_interval_seconds", "channel_ids")),
    CliCommandSpec(("index", "rebuild"), "handle_index_rebuild", (("json", "as_json"),)),
    CliCommandSpec(("search",), "handle_search", ("query", "limit", ("json", "as_json"))),
    CliCommandSpec(("context", "build"), "handle_context_build", ("query", "limit", "max_excerpt_chars", ("json", "as_json"))),
    CliCommandSpec(("evolution", "execute"), "handle_evolution_execute", ("run_id", "target_ids", "task_ids", "max_events")),
    CliCommandSpec(
        ("evolution", "request-followup"),
        "handle_evolution_request_followup",
        (
            "run_id",
            "candidate_id",
            "title",
            "summary",
            "requested_task_type",
            "slug",
            "target_ids",
            "owned_paths",
            "review_gates",
            "verification_obligation_json",
            "evidence_summary_json",
        ),
    ),
    CliCommandSpec(("evolution", "decide"), "handle_evolution_decide", ("task_id", "claim")),
    CliCommandSpec(("evolution", "run"), "handle_evolution_run", ("run_id",)),
    CliCommandSpec(("evolution", "status"), "handle_evolution_status", ("run_id",)),
    CliCommandSpec(("evolution", "report"), "handle_evolution_report", ("run_id",)),
    CliCommandSpec(("evolution", "compare"), "handle_evolution_compare", ("left_run_id", "right_run_id")),
    CliCommandSpec(
        ("status",),
        "handle_status",
        (("json", "as_json"), "only_open", "only_blocked", ("agents", "show_agents"), "stale_after_seconds"),
    ),
)

COMMAND_REGISTRY = MappingProxyType({spec.path: spec for spec in COMMAND_SPECS})


def command_path(args: Namespace) -> tuple[str, ...]:
    command = getattr(args, "command", None)
    if command == "plan":
        return (command, getattr(args, "plan_command", None))
    if command == "spec":
        return (command, getattr(args, "spec_command", None))
    if command == "subtasks":
        return (command, getattr(args, "subtasks_command", None))
    if command == "episode":
        return (command, getattr(args, "episode_command", None))
    if command == "eval":
        return (command, getattr(args, "eval_command", None))
    if command == "benchmark":
        return (command, getattr(args, "benchmark_command", None))
    if command == "dataset":
        return (command, getattr(args, "dataset_command", None))
    if command == "agent":
        return (command, getattr(args, "agent_command", None))
    if command == "ingest":
        return (command, getattr(args, "ingest_command", None))
    if command == "index":
        return (command, getattr(args, "index_command", None))
    if command == "context":
        return (command, getattr(args, "context_command", None))
    if command == "evolution":
        return (command, getattr(args, "evolution_command", None))
    return (command,)


def dispatch_command(
    args: Namespace,
    extras: Sequence[str],
    handlers: Mapping[str, CliHandler],
) -> int:
    path = command_path(args)
    spec = COMMAND_REGISTRY.get(path)
    if spec is None:
        raise UnknownCliCommandError("unknown command")
    handler = handlers[spec.handler_name]
    kwargs: dict[str, Any] = {}
    for binding in spec.argument_names:
        if isinstance(binding, tuple):
            arg_name, kwarg_name = binding
        else:
            arg_name = kwarg_name = binding
        kwargs[kwarg_name] = getattr(args, arg_name)
    kwargs.update(spec.constant_kwargs)
    if spec.extra_argument_name is not None:
        kwargs[spec.extra_argument_name] = list(extras)
    kwargs["repo_root"] = getattr(args, "repo_root", None)
    return handler(**kwargs)


def registered_command_paths() -> set[tuple[str, ...]]:
    return set(COMMAND_REGISTRY)


__all__ = [
    "COMMAND_REGISTRY",
    "COMMAND_SPECS",
    "CliCommandSpec",
    "UnknownCliCommandError",
    "command_path",
    "dispatch_command",
    "registered_command_paths",
]
