from __future__ import annotations

import argparse
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class TaskLaunchRequest:
    task_id: str
    agent_id: str
    role: str
    step: str | None
    summary: str | None
    instruction: str | None
    owned_paths: tuple[str, ...]
    heartbeat_seconds: int
    provider_args: tuple[str, ...]
    command: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ConversationLaunchRequest:
    message: str
    title: str | None
    task_type: str
    slug: str | None
    agent_id: str
    role: str
    instruction: str | None
    owned_paths: tuple[str, ...]
    provider_args: tuple[str, ...]


def parse_provider_wrapper_request(
    provider: str,
    argv: list[str],
) -> TaskLaunchRequest | ConversationLaunchRequest:
    parser = argparse.ArgumentParser(prog=f"{provider}-agent-wrapper")
    subparsers = parser.add_subparsers(dest="launch_mode", required=True)

    task_parser = subparsers.add_parser("task")
    task_parser.add_argument("task_id")
    task_parser.add_argument("agent_id")
    task_parser.add_argument("--role", default="worker")
    task_parser.add_argument("--step")
    task_parser.add_argument("--summary")
    task_parser.add_argument("--instruction")
    task_parser.add_argument("--owned-path", action="append", dest="owned_paths")
    task_parser.add_argument("--heartbeat-seconds", type=int, default=10)
    task_parser.add_argument("--provider-arg", action="append", dest="provider_args")

    conversation_parser = subparsers.add_parser("conversation")
    conversation_parser.add_argument("message")
    conversation_parser.add_argument("--title")
    conversation_parser.add_argument("--task-type", choices=["feature", "issue"], default="feature")
    conversation_parser.add_argument("--slug")
    conversation_parser.add_argument("--agent-id", default="worker-1")
    conversation_parser.add_argument("--role", default="worker")
    conversation_parser.add_argument("--instruction")
    conversation_parser.add_argument("--owned-path", action="append", dest="owned_paths")
    conversation_parser.add_argument("--provider-arg", action="append", dest="provider_args")

    args, extras = parser.parse_known_args(_normalize_wrapper_argv(argv))
    if args.launch_mode == "conversation":
        return ConversationLaunchRequest(
            message=args.message,
            title=args.title,
            task_type=args.task_type,
            slug=args.slug,
            agent_id=args.agent_id,
            role=args.role,
            instruction=args.instruction,
            owned_paths=tuple(args.owned_paths or ()),
            provider_args=tuple(args.provider_args or ()),
        )

    command = list(extras)
    if command and command[0] == "--":
        command = command[1:]
    return TaskLaunchRequest(
        task_id=args.task_id,
        agent_id=args.agent_id,
        role=args.role,
        step=args.step,
        summary=args.summary,
        instruction=args.instruction,
        owned_paths=tuple(args.owned_paths or ()),
        heartbeat_seconds=args.heartbeat_seconds,
        provider_args=tuple(args.provider_args or ()),
        command=tuple(command),
    )


def _normalize_wrapper_argv(argv: list[str]) -> list[str]:
    if argv and argv[0] in {"task", "conversation"}:
        return list(argv)
    return ["task", *argv]


__all__ = [
    "ConversationLaunchRequest",
    "TaskLaunchRequest",
    "parse_provider_wrapper_request",
]
