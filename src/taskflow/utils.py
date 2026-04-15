from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import datetime, timezone


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def project_fields(
    source: Mapping[str, object],
    field_defaults: Mapping[str, object | Callable[[], object]],
) -> dict[str, object]:
    projected: dict[str, object] = {}
    for field, default in field_defaults.items():
        if field in source:
            projected[field] = source[field]
            continue
        projected[field] = default() if callable(default) else default
    return projected


def find_unknown_fields(
    changes: Mapping[str, object],
    allowed_fields: set[str] | frozenset[str],
) -> list[str]:
    return sorted(set(changes) - set(allowed_fields))
