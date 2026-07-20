from __future__ import annotations

from pathlib import Path

from ..application.use_cases.inbox_processing import InboxProcessingService
from ..infra.config.loader import SisyphusConfig
from .inbox import build_inbox_processing_service
from .inbox_handlers import (
    build_conversation_event_service,
    build_pull_request_merged_event_service,
)


def build_repository_inbox_processing_service(
    repo_root: Path,
    config: SisyphusConfig,
) -> InboxProcessingService:
    conversation = build_conversation_event_service(repo_root, config)
    pull_request_merged = build_pull_request_merged_event_service(repo_root, config)
    return build_inbox_processing_service(
        repo_root,
        config,
        handlers={
            "conversation": conversation.process,
            "pull_request_merged": pull_request_merged.process,
        },
    )


__all__ = ["build_repository_inbox_processing_service"]
