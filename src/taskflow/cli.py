from __future__ import annotations

import argparse
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
from .agent_runtime import run_tracked_agent
from .audit import run_verify
from .closeout import run_close
from .config import load_config
from .creation import TaskCreationError, create_task_workspace
from .daemon import queue_conversation_event, run_daemon
from .discovery import detect_repo_root
from .state import list_task_records


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="taskflow")
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

    ingest_parser = subparsers.add_parser("ingest")
    ingest_subparsers = ingest_parser.add_subparsers(dest="ingest_command", required=True)
    ingest_conversation_parser = ingest_subparsers.add_parser("conversation")
    ingest_conversation_parser.add_argument("message")
    ingest_conversation_parser.add_argument("--title")
    ingest_conversation_parser.add_argument("--task-type", choices=["feature", "issue"], default="feature")
    ingest_conversation_parser.add_argument("--slug")
    ingest_conversation_parser.add_argument("--instruction")
    ingest_conversation_parser.add_argument("--agent-id", default="worker-1")
    ingest_conversation_parser.add_argument("--role", default="worker")
    ingest_conversation_parser.add_argument("--provider", default="codex")
    ingest_conversation_parser.add_argument("--owned-path", action="append", dest="owned_paths")
    ingest_conversation_parser.add_argument("--provider-arg", action="append", dest="provider_args")
    ingest_conversation_parser.add_argument("--no-run", action="store_true")

    daemon_parser = subparsers.add_parser("daemon")
    daemon_parser.add_argument("--once", action="store_true")
    daemon_parser.add_argument("--poll-interval-seconds", type=int, default=5)
    daemon_parser.add_argument("--max-events", type=int)

    status_parser = subparsers.add_parser("status")
    status_parser.add_argument("--json", action="store_true")
    status_parser.add_argument("--open", dest="only_open", action="store_true")
    status_parser.add_argument("--blocked", dest="only_blocked", action="store_true")
    status_parser.add_argument("--agents", action="store_true")
    status_parser.add_argument("--stale-after-seconds", type=int, default=DEFAULT_STALE_AFTER_SECONDS)

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


def handle_new(task_type: str, slug: str) -> int:
    repo_root = detect_repo_root(Path.cwd())
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
    return 0


def handle_verify(task_id: str) -> int:
    repo_root = detect_repo_root(Path.cwd())
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


def handle_close(task_id: str, allow_dirty: bool) -> int:
    repo_root = detect_repo_root(Path.cwd())
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
    no_run: bool,
) -> int:
    repo_root = detect_repo_root(Path.cwd())
    try:
        event, event_path = queue_conversation_event(
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
            auto_run=not no_run,
        )
    except RuntimeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    print(f"queued {event['id']}")
    print(f"event_file: {event_path}")
    print(f"task_type: {event['payload']['task_type']}")
    print(f"slug: {event['payload']['slug']}")
    return 0


def handle_daemon(once: bool, poll_interval_seconds: int, max_events: int | None) -> int:
    repo_root = detect_repo_root(Path.cwd())
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
    return 0 if stats.failed == 0 else 1


def handle_agents(task_id: str | None, as_json: bool, stale_after_seconds: int) -> int:
    repo_root = detect_repo_root(Path.cwd())
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
) -> int:
    repo_root = detect_repo_root(Path.cwd())
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
) -> int:
    repo_root = detect_repo_root(Path.cwd())
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
) -> int:
    repo_root = detect_repo_root(Path.cwd())
    config = load_config(repo_root)
    if command and command[0] == "--":
        command = command[1:]
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
            run_cwd=Path.cwd(),
            stdin_text=stdin_text,
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
) -> int:
    repo_root = detect_repo_root(Path.cwd())
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
        print(
            f"{task.get('id')} "
            f"[{task.get('type')}] "
            f"status={task.get('status')} "
            f"stage={task.get('stage')} "
            f"audit={task.get('audit_attempts', 0)}/{task.get('max_audit_attempts', 10)} "
            f"gates={gate_count}"
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


def main() -> int:
    parser = build_parser()
    args, extras = parser.parse_known_args()
    if not (args.command == "agent" and getattr(args, "agent_command", None) == "run") and extras:
        parser.error(f"unrecognized arguments: {' '.join(extras)}")

    if args.command == "new":
        return handle_new(task_type=args.task_type, slug=args.slug)
    if args.command == "verify":
        return handle_verify(task_id=args.task_id)
    if args.command == "close":
        return handle_close(task_id=args.task_id, allow_dirty=args.allow_dirty)
    if args.command == "agents":
        return handle_agents(
            task_id=args.task_id,
            as_json=args.json,
            stale_after_seconds=args.stale_after_seconds,
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
            )
        if args.agent_command == "finish":
            return handle_agent_finish(
                task_id=args.task_id,
                agent_id=args.agent_id,
                status=args.status,
                summary=args.summary,
                error=args.error,
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
                no_run=args.no_run,
            )
    if args.command == "daemon":
        return handle_daemon(
            once=args.once,
            poll_interval_seconds=args.poll_interval_seconds,
            max_events=args.max_events,
        )
    if args.command == "status":
        return handle_status(
            as_json=args.json,
            only_open=args.only_open,
            only_blocked=args.only_blocked,
            show_agents=args.agents,
            stale_after_seconds=args.stale_after_seconds,
        )

    parser.error("unknown command")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
