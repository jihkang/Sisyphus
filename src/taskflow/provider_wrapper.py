from __future__ import annotations

import argparse
from pathlib import Path
import shutil
import sys

from .codex_prompt import build_codex_prompt
from .config import load_config
from .discovery import detect_repo_root


def run_provider_wrapper(provider: str, argv: list[str], *, repo_root: Path | None = None) -> int:
    from .cli import handle_agent_run

    repo_root = repo_root or detect_repo_root(Path.cwd())
    config = load_config(repo_root)
    normalized_argv = _normalize_wrapper_argv(argv)
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
    task_parser.add_argument("command", nargs=argparse.REMAINDER)

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

    args = parser.parse_args(normalized_argv)

    if args.launch_mode == "conversation":
        return _run_conversation_mode(
            provider=provider,
            repo_root=repo_root,
            config=config,
            message=args.message,
            title=args.title,
            task_type=args.task_type,
            slug=args.slug,
            agent_id=args.agent_id,
            role=args.role,
            instruction=args.instruction,
            owned_paths=args.owned_paths,
            provider_args=args.provider_args,
        )

    command = list(args.command)
    stdin_text: str | None = None
    step = args.step
    summary = args.summary

    if command and command[0] == "--":
        command = command[1:]

    if not command:
        command, stdin_text, default_step, default_summary = _build_default_launch(
            provider=provider,
            repo_root=repo_root,
            config=config,
            task_id=args.task_id,
            extra_instruction=args.instruction,
            provider_args=args.provider_args or [],
        )
        step = step or default_step
        summary = summary or default_summary

    return handle_agent_run(
        task_id=args.task_id,
        agent_id=args.agent_id,
        role=args.role,
        provider=provider,
        step=step,
        summary=summary,
        owned_paths=args.owned_paths,
        heartbeat_seconds=args.heartbeat_seconds,
        command=command,
        stdin_text=stdin_text,
    )


def _run_conversation_mode(
    *,
    provider: str,
    repo_root: Path,
    config,
    message: str,
    title: str | None,
    task_type: str,
    slug: str | None,
    agent_id: str,
    role: str,
    instruction: str | None,
    owned_paths: list[str] | None,
    provider_args: list[str] | None,
) -> int:
    from .daemon import process_inbox_event, queue_conversation_event

    event, event_path = queue_conversation_event(
        repo_root,
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
        auto_run=True,
    )
    processed = process_inbox_event(
        repo_root=repo_root,
        config=config,
        event_path=event_path,
    )
    if processed.get("status") != "processed":
        print(f"error: {processed.get('error') or 'conversation task launch failed'}", file=sys.stderr)
        return 1

    result = processed.get("result", {})
    print(f"created {result.get('task_id')}")
    print(f"branch: {result.get('branch')}")
    print(f"worktree_path: {result.get('worktree_path')}")
    if result.get("agent_id"):
        print(f"agent_id: {result.get('agent_id')}")
    return 0


def _build_default_launch(
    *,
    provider: str,
    repo_root: Path,
    config,
    task_id: str,
    extra_instruction: str | None,
    provider_args: list[str],
) -> tuple[list[str], str | None, str, str]:
    if provider != "codex":
        raise RuntimeError(f"default launch is not configured for provider: {provider}")

    codex = _resolve_codex_executable()
    prompt = build_codex_prompt(
        repo_root=repo_root,
        config=config,
        task_id=task_id,
        extra_instruction=extra_instruction,
    )
    command = [
        codex,
        "exec",
        "-C",
        str(prompt.workdir),
        *provider_args,
        "-",
    ]
    return (
        command,
        prompt.prompt,
        f"running codex task {task_id}",
        f"codex exec started for {task_id}",
    )


def _resolve_codex_executable() -> str:
    for candidate in ("codex.cmd", "codex"):
        resolved = shutil.which(candidate)
        if resolved:
            return resolved
    raise RuntimeError("could not find local codex executable")


def _normalize_wrapper_argv(argv: list[str]) -> list[str]:
    if argv and argv[0] in {"task", "conversation"}:
        return list(argv)
    return ["task", *argv]
