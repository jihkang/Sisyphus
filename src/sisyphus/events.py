from __future__ import annotations

from .application.codecs.events import encode_event_envelope, encode_event_envelope_json
from .application.events import (
    SCHEMA_VERSION,
    EventEnvelope,
    new_event_envelope,
    new_event_id,
    normalize_event_envelope,
    utc_now,
)
from .compat.serialization import install_serialization_compat


install_serialization_compat(
    EventEnvelope,
    encode_mapping=encode_event_envelope,
    encode_json=encode_event_envelope_json,
)

__all__ = [
    "SCHEMA_VERSION",
    "EventEnvelope",
    "encode_event_envelope",
    "encode_event_envelope_json",
    "new_event_envelope",
    "new_event_id",
    "normalize_event_envelope",
    "utc_now",
]
