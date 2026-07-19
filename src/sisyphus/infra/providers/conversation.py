from __future__ import annotations

from pathlib import Path
import sys

from ...application.commands.inbox import QueueConversationCommand
from ...application.use_cases.inbox import InboxQueueService
from ...application.use_cases.inbox_processing import InboxProcessingService
from ..config.loader import SisyphusConfig


def run_legacy_conversation(
    *,
    provider: str,
    repo_root: Path,
    config: SisyphusConfig,
    queue: InboxQueueService,
    processor: InboxProcessingService,
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
    _ = repo_root, config
    _, event_path = queue.queue_conversation(
        QueueConversationCommand(
            message=message,
            title=title,
            task_type=task_type,
            slug=slug,
            instruction=instruction,
            agent_id=agent_id,
            role=role,
            provider=provider,
            owned_paths=tuple(owned_paths or ()),
            provider_args=tuple(provider_args or ()),
            auto_run=True,
        )
    )
    processed = processor.process(event_path)
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
