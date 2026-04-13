from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from collections.abc import Mapping
import json
import uuid


SCHEMA_VERSION = "taskflow.event.v1"


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def new_event_id() -> str:
    return f"evt_{uuid.uuid4().hex}"


@dataclass(slots=True)
class EventEnvelope:
    event_type: str
    data: dict[str, object] = field(default_factory=dict)
    source: dict[str, object] = field(default_factory=dict)
    event_id: str = field(default_factory=new_event_id)
    timestamp: str = field(default_factory=utc_now)
    schema_version: str = SCHEMA_VERSION

    def to_dict(self) -> dict[str, object]:
        return {
            "event_id": self.event_id,
            "event_type": self.event_type,
            "timestamp": self.timestamp,
            "schema_version": self.schema_version,
            "source": dict(self.source),
            "data": dict(self.data),
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), separators=(",", ":"))


def new_event_envelope(
    event_type: str,
    *,
    data: Mapping[str, object] | None = None,
    source: Mapping[str, object] | None = None,
    event_id: str | None = None,
    timestamp: str | None = None,
    schema_version: str = SCHEMA_VERSION,
) -> EventEnvelope:
    return EventEnvelope(
        event_type=event_type,
        data=dict(data or {}),
        source=dict(source or {}),
        event_id=event_id or new_event_id(),
        timestamp=timestamp or utc_now(),
        schema_version=schema_version,
    )


def normalize_event_envelope(event: EventEnvelope | Mapping[str, object]) -> EventEnvelope:
    if isinstance(event, EventEnvelope):
        return event

    event_type = str(event.get("event_type", "")).strip()
    if not event_type:
        raise ValueError("event envelope requires an event_type")
    return EventEnvelope(
        event_type=event_type,
        data=dict(event.get("data", {})) if isinstance(event.get("data", {}), Mapping) else {},
        source=dict(event.get("source", {})) if isinstance(event.get("source", {}), Mapping) else {},
        event_id=str(event.get("event_id", "")).strip() or new_event_id(),
        timestamp=str(event.get("timestamp", "")).strip() or utc_now(),
        schema_version=str(event.get("schema_version", SCHEMA_VERSION)).strip() or SCHEMA_VERSION,
    )
