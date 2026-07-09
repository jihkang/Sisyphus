from __future__ import annotations


def dict_list(value: object) -> list[dict[str, object]] | None:
    if value is None:
        return None
    if not isinstance(value, list):
        raise TypeError(f"expected list value, got: {type(value).__name__}")
    normalized: list[dict[str, object]] = []
    for item in value:
        if not isinstance(item, dict):
            raise TypeError("expected changed_files entries to be objects")
        normalized.append({str(key): item[key] for key in item})
    return normalized


__all__ = ["dict_list"]
