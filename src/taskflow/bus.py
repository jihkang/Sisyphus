from __future__ import annotations

from pathlib import Path
from typing import Protocol

from .config import TaskflowConfig
from .events import EventEnvelope, normalize_event_envelope


class EventPublisher(Protocol):
    def publish(self, event: EventEnvelope | dict[str, object]) -> None:
        ...


class NoopEventPublisher:
    def publish(self, event: EventEnvelope | dict[str, object]) -> None:
        normalize_event_envelope(event)


def build_event_publisher(repo_root: Path, config: TaskflowConfig) -> EventPublisher:
    provider = config.event_bus.provider
    if provider in {"", "noop", "none", "disabled"}:
        return NoopEventPublisher()
    if provider == "jsonl":
        from .bus_jsonl import JsonlEventPublisher, resolve_event_bus_path

        return JsonlEventPublisher(resolve_event_bus_path(repo_root, config))
    raise ValueError(f"unsupported event bus provider: {provider}")
