from __future__ import annotations

from importlib import import_module
from pathlib import Path
import sys


def run_legacy_conversation(
    *,
    provider: str,
    repo_root: Path,
    config: object,
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
    daemon = import_module("sisyphus.daemon")
    _, event_path = daemon.queue_conversation_event(
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
    processed = daemon.process_inbox_event(
        repo_root=repo_root,
        config=config,
        event_path=event_path,
    )
    if processed.get("status") != "processed":
        error = processed.get("error") or "conversation task launch failed"
        print(f"error: {error}", file=sys.stderr)
        return 1

    result = processed.get("result", {})
    print("created {}".format(result.get("task_id")))
    print("branch: {}".format(result.get("branch")))
    print("worktree_path: {}".format(result.get("worktree_path")))
    if result.get("agent_id"):
        print("agent_id: {}".format(result.get("agent_id")))
    return 0


__all__ = ["run_legacy_conversation"]
