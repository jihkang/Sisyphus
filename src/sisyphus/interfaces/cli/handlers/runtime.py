from __future__ import annotations

from pathlib import Path
import sys

from ....config import SisyphusConfig
from ....creation import TaskCreationError, create_task_workspace
from ....daemon import run_daemon
from ....service import run_service


def handle_new(*, repo_root: Path, config: SisyphusConfig, task_type: str, slug: str) -> int:
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


def handle_daemon(
    *,
    repo_root: Path,
    config: SisyphusConfig,
    once: bool,
    poll_interval_seconds: int,
    max_events: int | None,
) -> int:
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


def handle_serve(*, repo_root: Path, config: SisyphusConfig, poll_interval_seconds: int) -> int:
    run_service(
        repo_root=repo_root,
        config=config,
        poll_interval_seconds=poll_interval_seconds,
    )
    return 0


def handle_discord_bot(
    *,
    repo_root: Path,
    config: SisyphusConfig,
    token: str | None,
    poll_interval_seconds: int,
    channel_ids: list[int] | None,
) -> int:
    from ....discord_bot import run_discord_bot

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


__all__ = [
    "handle_daemon",
    "handle_discord_bot",
    "handle_new",
    "handle_serve",
]
