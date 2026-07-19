from __future__ import annotations

from collections.abc import Mapping, Sequence

from ...shared.mappings import find_unknown_fields


def require_mapping(value: object, field_name: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise TypeError(f"{field_name} must be a mapping, got {type(value).__name__}")
    return value


def require_list(value: object, field_name: str) -> list[object]:
    if not isinstance(value, list):
        raise TypeError(f"{field_name} must be a list, got {type(value).__name__}")
    return value


def optional_string(value: object) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip()
    return normalized or None


def require_string(value: object, field_name: str) -> str:
    normalized = optional_string(value)
    if normalized is None:
        raise ValueError(f"{field_name} is required")
    return normalized


def optional_int(value: object, field_name: str) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{field_name} must be int")
    return value


def reject_unknown_fields(
    mapping: Mapping[str, object],
    allowed_fields: frozenset[str],
    field_name: str,
) -> None:
    unknown = find_unknown_fields(mapping, allowed_fields)
    if unknown:
        raise ValueError(f"{field_name} contains unknown fields: {', '.join(unknown)}")


def decode_mapping_tuple(value: object, decoder, field_name: str) -> tuple[object, ...]:
    items = require_list(value, field_name)
    return tuple(
        decoder(require_mapping(item, f"{field_name}[{index}]"))
        for index, item in enumerate(items)
    )


def decode_string_tuple(value: object, field_name: str) -> tuple[str, ...]:
    values = require_list(value, field_name)
    return tuple(require_string(item, f"{field_name}[{index}]") for index, item in enumerate(values))


def decode_ref_tuple(value: object, field_name: str) -> tuple[str, ...]:
    values = decode_string_tuple(value, field_name)
    for index, item in enumerate(values):
        if "://" not in item:
            raise ValueError(f"{field_name}[{index}] must be a URI-like ref")
    return values


def normalize_json_mapping(value: object, field_name: str) -> dict[str, object]:
    mapping = require_mapping(value, field_name)
    return {
        str(key): normalize_json_value(item, f"{field_name}.{key}")
        for key, item in sorted(mapping.items(), key=lambda pair: str(pair[0]))
    }


def normalize_json_value(value: object, field_name: str) -> object:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Mapping):
        return normalize_json_mapping(value, field_name)
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [
            normalize_json_value(item, f"{field_name}[{index}]")
            for index, item in enumerate(value)
        ]
    raise TypeError(f"{field_name} must be JSON-serializable")


__all__ = [
    "decode_mapping_tuple",
    "decode_ref_tuple",
    "decode_string_tuple",
    "normalize_json_mapping",
    "normalize_json_value",
    "optional_int",
    "optional_string",
    "reject_unknown_fields",
    "require_list",
    "require_mapping",
    "require_string",
]
