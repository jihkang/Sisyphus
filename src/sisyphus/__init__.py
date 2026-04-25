from __future__ import annotations

from .api import (
    MergeRecordResult,
    PromotionExecutionResult,
    QueuedConversation,
    TaskRequestResult,
    execute_promotion,
    get_task,
    list_tasks,
    queue_conversation,
    record_merged_pull_request,
    request_task,
    run_until_stable,
)

__version__ = "0.1.0"

__all__ = [
    "__version__",
    "MergeRecordResult",
    "PromotionExecutionResult",
    "QueuedConversation",
    "TaskRequestResult",
    "execute_promotion",
    "get_task",
    "list_tasks",
    "queue_conversation",
    "record_merged_pull_request",
    "request_task",
    "run_until_stable",
]
