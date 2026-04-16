"""Legacy taskflow compatibility package for Sisyphus."""

from .api import (
    QueuedConversation,
    TaskRequestResult,
    get_task,
    list_tasks,
    queue_conversation,
    request_task,
    run_until_stable,
)

__all__ = [
    "__version__",
    "QueuedConversation",
    "TaskRequestResult",
    "get_task",
    "list_tasks",
    "queue_conversation",
    "request_task",
    "run_until_stable",
]

__version__ = "0.1.0"
