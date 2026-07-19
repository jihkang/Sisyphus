from __future__ import annotations

import json

from ..events import EventEnvelope


def encode_event_envelope(value: EventEnvelope) -> dict[str, object]:
    return {
        "event_id": value.event_id,
        "event_type": value.event_type,
        "timestamp": value.timestamp,
        "schema_version": value.schema_version,
        "source": dict(value.source),
        "data": dict(value.data),
    }


def encode_event_envelope_json(value: EventEnvelope) -> str:
    return json.dumps(encode_event_envelope(value), separators=(",", ":"))


__all__ = ["encode_event_envelope", "encode_event_envelope_json"]
