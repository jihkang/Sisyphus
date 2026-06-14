from __future__ import annotations

from collections.abc import Mapping
import hashlib
import json
from typing import Any


def stable_json_hash(payload: Mapping[str, object]) -> str:
    rendered = json.dumps(_json_safe(payload), separators=(",", ":"), sort_keys=True)
    return f"sha256:{hashlib.sha256(rendered.encode('utf-8')).hexdigest()}"


def _json_safe(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    return value


__all__ = ["stable_json_hash"]
