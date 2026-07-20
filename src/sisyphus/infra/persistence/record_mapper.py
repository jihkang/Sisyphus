from __future__ import annotations

from collections.abc import Callable, Mapping
from copy import deepcopy
from dataclasses import dataclass, fields
from typing import Generic, TypeVar

from ...shared.serialization import JsonValue, to_json_value


ModelT = TypeVar("ModelT")
Decode = Callable[[object], object]
Encode = Callable[[object], object]


def _identity(value: object) -> object:
    return value


@dataclass(frozen=True, slots=True)
class FieldMapping:
    attribute: str
    decode: Decode = _identity
    encode: Encode = _identity


@dataclass(frozen=True, slots=True)
class RecordEnvelope(Generic[ModelT]):
    model: ModelT
    extensions: dict[str, object]
    present_fields: frozenset[str]
    field_order: tuple[str, ...] = ()


class DataclassRecordMapper(Generic[ModelT]):
    """Centralize dataclass persistence without putting to_dict on entities."""

    def __init__(
        self,
        model_type: type[ModelT],
        field_mappings: Mapping[str, FieldMapping],
    ) -> None:
        model_fields = {field.name for field in fields(model_type)}
        mapped_attributes = [mapping.attribute for mapping in field_mappings.values()]
        unknown_attributes = set(mapped_attributes) - model_fields
        duplicate_attributes = {
            attribute for attribute in mapped_attributes if mapped_attributes.count(attribute) > 1
        }
        if unknown_attributes:
            names = ", ".join(sorted(unknown_attributes))
            raise ValueError(f"field mappings reference unknown model attributes: {names}")
        if duplicate_attributes:
            names = ", ".join(sorted(duplicate_attributes))
            raise ValueError(f"model attributes have duplicate record mappings: {names}")
        self._model_type = model_type
        self._field_mappings = dict(field_mappings)

    def decode(self, record: Mapping[str, object]) -> RecordEnvelope[ModelT]:
        if not isinstance(record, Mapping):
            raise TypeError("record must be a mapping")
        model_values: dict[str, object] = {}
        for record_key, mapping in self._field_mappings.items():
            if record_key not in record:
                continue
            model_values[mapping.attribute] = mapping.decode(deepcopy(record[record_key]))
        extensions = {
            key: deepcopy(value)
            for key, value in record.items()
            if key not in self._field_mappings
        }
        return RecordEnvelope(
            model=self._model_type(**model_values),
            extensions=extensions,
            present_fields=frozenset(key for key in self._field_mappings if key in record),
            field_order=tuple(record),
        )

    def encode(
        self,
        envelope: RecordEnvelope[ModelT],
        *,
        include_defaults: bool = False,
    ) -> dict[str, JsonValue]:
        extensions = to_json_value(deepcopy(envelope.extensions))
        if not isinstance(extensions, dict):
            raise TypeError("record extensions must encode to a JSON object")
        encoded_fields: dict[str, JsonValue] = {}
        for record_key, mapping in self._field_mappings.items():
            if not include_defaults and record_key not in envelope.present_fields:
                continue
            value = mapping.encode(getattr(envelope.model, mapping.attribute))
            encoded_fields[record_key] = to_json_value(value)

        values = {**extensions, **encoded_fields}
        record: dict[str, JsonValue] = {}
        for record_key in envelope.field_order:
            if record_key in values:
                record[record_key] = values.pop(record_key)
        record.update(values)
        return record

    def envelope_for(self, model: ModelT) -> RecordEnvelope[ModelT]:
        return RecordEnvelope(
            model=model,
            extensions={},
            present_fields=frozenset(self._field_mappings),
            field_order=tuple(self._field_mappings),
        )


__all__ = [
    "DataclassRecordMapper",
    "FieldMapping",
    "RecordEnvelope",
]
