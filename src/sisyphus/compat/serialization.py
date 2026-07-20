from __future__ import annotations

from collections.abc import Callable, Mapping


MappingEncoder = Callable[[object], dict[str, object]]
MappingDecoder = Callable[[Mapping[str, object]], object]
JsonEncoder = Callable[[object], str]


def install_serialization_compat(
    model: type[object],
    *,
    encode_mapping: MappingEncoder | None = None,
    decode_mapping: MappingDecoder | None = None,
    encode_json: JsonEncoder | None = None,
) -> None:
    """Restore legacy model methods at an outer compatibility boundary."""

    if encode_mapping is not None and "to_dict" not in model.__dict__:

        def to_dict(self: object) -> dict[str, object]:
            return encode_mapping(self)

        to_dict.__name__ = "to_dict"
        to_dict.__qualname__ = f"{model.__qualname__}.to_dict"
        setattr(model, "to_dict", to_dict)

    if decode_mapping is not None and "from_dict" not in model.__dict__:

        def from_dict(
            _model: type[object],
            raw: Mapping[str, object],
        ) -> object:
            return decode_mapping(raw)

        from_dict.__name__ = "from_dict"
        from_dict.__qualname__ = f"{model.__qualname__}.from_dict"
        setattr(model, "from_dict", classmethod(from_dict))

    if encode_json is not None and "to_json" not in model.__dict__:

        def to_json(self: object) -> str:
            return encode_json(self)

        to_json.__name__ = "to_json"
        to_json.__qualname__ = f"{model.__qualname__}.to_json"
        setattr(model, "to_json", to_json)


__all__ = ["install_serialization_compat"]
