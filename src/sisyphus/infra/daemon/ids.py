from __future__ import annotations

import uuid


def new_event_id() -> str:
    return f"evt-{uuid.uuid4().hex[:12]}"


__all__ = ["new_event_id"]
