from __future__ import annotations

from pathlib import Path
import os

from ...shared.paths import (
    inbox_failed_dir,
    inbox_pending_dir,
    inbox_processed_dir,
    inbox_processing_dir,
)
from .json_store import read_json_file, write_json_file


class InboxRepository:
    """Owns atomic inbox persistence and lifecycle moves."""

    def __init__(self, repo_root: Path) -> None:
        self.repo_root = repo_root

    def enqueue(self, event: dict[str, object]) -> Path:
        event_id = str(event["id"])
        event_path = inbox_pending_dir(self.repo_root) / f"{event_id}.json"
        write_json_file(event_path, event)
        return event_path

    def list_processable(self) -> list[Path]:
        processing = sorted(inbox_processing_dir(self.repo_root).glob("*.json"))
        pending = sorted(inbox_pending_dir(self.repo_root).glob("*.json"))
        return [*processing, *pending]

    def claim(self, event_path: Path) -> Path:
        processing_dir = inbox_processing_dir(self.repo_root)
        if event_path.parent == processing_dir:
            return event_path
        if event_path.parent != inbox_pending_dir(self.repo_root):
            raise ValueError(f"event path is outside the processable inbox: {event_path}")
        processing_dir.mkdir(parents=True, exist_ok=True)
        claimed_path = processing_dir / event_path.name
        os.replace(event_path, claimed_path)
        return claimed_path

    def read(self, event_path: Path) -> object:
        return read_json_file(event_path)

    def update(self, event_path: Path, event: dict[str, object]) -> None:
        write_json_file(event_path, event)

    def complete(self, event_path: Path, event: dict[str, object]) -> Path:
        return self._finish(event_path, event, inbox_processed_dir(self.repo_root))

    def fail(self, event_path: Path, event: dict[str, object]) -> Path:
        return self._finish(event_path, event, inbox_failed_dir(self.repo_root))

    def _finish(self, event_path: Path, event: dict[str, object], destination_dir: Path) -> Path:
        self.update(event_path, event)
        destination_dir.mkdir(parents=True, exist_ok=True)
        destination = destination_dir / event_path.name
        os.replace(event_path, destination)
        return destination


__all__ = ["InboxRepository"]
