from __future__ import annotations


def required_str(value: object, field_name: str) -> str:
    if value in (None, ""):
        raise ValueError(f"{field_name} is required")
    return str(value)


def optional_str(value: object) -> str | None:
    if value in (None, ""):
        return None
    return str(value)


def optional_str_list(value: object) -> list[str] | None:
    if value is None:
        return None
    if not isinstance(value, list):
        raise TypeError(f"expected list value, got: {type(value).__name__}")
    return [str(item) for item in value]
