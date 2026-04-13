from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path

from .config import TaskflowConfig
from .events import EventEnvelope, normalize_event_envelope
from .paths import event_log_file


@dataclass(slots=True)
class JsonlEventPublisher:
    path: Path

    def publish(self, event: EventEnvelope | dict[str, object]) -> None:
        envelope = normalize_event_envelope(event)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(envelope.to_json())
            handle.write("\n")


def resolve_event_bus_path(repo_root: Path, config: TaskflowConfig) -> Path:
    configured = config.event_bus.jsonl_path.strip()
    if not configured:
        return event_log_file(repo_root)

    candidate = Path(configured)
    if candidate.is_absolute():
        return candidate
    return repo_root / candidate


def read_jsonl_events(path: Path, *, limit: int = 50) -> list[dict[str, object]]:
    if limit < 1:
        return []
    if not path.exists():
        return []

    lines = path.read_text(encoding="utf-8").splitlines()
    selected = lines[-limit:]
    events: list[dict[str, object]] = []
    for line in selected:
        line = line.strip()
        if not line:
            continue
        events.append(dict(json.loads(line)))
    return events
