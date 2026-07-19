from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
from typing import Protocol, TextIO

from ...events import EventEnvelope, normalize_event_envelope
from ...shared.paths import event_log_file
from ..config.loader import SisyphusConfig
from ..persistence.atomic_text import fsync_directory
from ..persistence.file_lock import file_handle_lock


class EventPublisher(Protocol):
    def publish(self, event: EventEnvelope | dict[str, object]) -> None: ...


class NoopEventPublisher:
    def publish(self, event: EventEnvelope | dict[str, object]) -> None:
        normalize_event_envelope(event)


@dataclass(slots=True)
class JsonlEventPublisher:
    path: Path

    def publish(self, event: EventEnvelope | dict[str, object]) -> None:
        envelope = normalize_event_envelope(event)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        handle, created = _open_append_stream(self.path)
        with handle:
            with file_handle_lock(handle):
                handle.seek(0, os.SEEK_END)
                handle.write(envelope.to_json())
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
        if created:
            fsync_directory(self.path.parent)


def build_event_publisher(repo_root: Path, config: SisyphusConfig) -> EventPublisher:
    provider = config.event_bus.provider
    if provider in {"", "noop", "none", "disabled"}:
        return NoopEventPublisher()
    if provider == "jsonl":
        return JsonlEventPublisher(resolve_event_bus_path(repo_root, config))
    raise ValueError(f"unsupported event bus provider: {provider}")


def resolve_event_bus_path(repo_root: Path, config: SisyphusConfig) -> Path:
    configured = config.event_bus.jsonl_path.strip()
    if not configured:
        return event_log_file(repo_root)

    candidate = Path(configured)
    if candidate.is_absolute():
        return candidate
    return repo_root / candidate


def read_jsonl_events(path: Path, *, limit: int = 50) -> list[dict[str, object]]:
    if limit < 1 or not path.exists():
        return []

    with _open_read_stream(path) as handle, file_handle_lock(handle):
        lines = handle.read().splitlines()
    selected = lines[-limit:]
    events: list[dict[str, object]] = []
    for line in selected:
        line = line.strip()
        if line:
            events.append(dict(json.loads(line)))
    return events


def _open_append_stream(path: Path) -> tuple[TextIO, bool]:
    flags = (
        os.O_RDWR
        | os.O_APPEND
        | getattr(os, "O_CLOEXEC", 0)
        | getattr(os, "O_NOFOLLOW", 0)
    )
    try:
        descriptor = os.open(path, flags | os.O_CREAT | os.O_EXCL, 0o666)
        created = True
    except FileExistsError:
        descriptor = os.open(path, flags)
        created = False
    return os.fdopen(descriptor, "a+", encoding="utf-8"), created


def _open_read_stream(path: Path) -> TextIO:
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(path, flags)
    return os.fdopen(descriptor, "r", encoding="utf-8")


__all__ = [
    "EventPublisher",
    "JsonlEventPublisher",
    "NoopEventPublisher",
    "build_event_publisher",
    "read_jsonl_events",
    "resolve_event_bus_path",
]
