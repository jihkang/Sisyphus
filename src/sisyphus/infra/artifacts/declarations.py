from __future__ import annotations

from importlib import resources
import json

from ...application.codecs.artifact_dsl import (
    decode_protocol_spec,
)
from ...application.codecs.execution_policies import decode_execution_policy_registry
from ...domain.artifact.dsl import ExecutionPolicy, ProtocolSpec


def load_feature_change_protocol_declaration(relative_path: str) -> ProtocolSpec:
    return decode_protocol_spec(_load_json_declaration(relative_path))


def load_execution_policy_declaration(
    relative_path: str,
) -> dict[str, ExecutionPolicy]:
    return decode_execution_policy_registry(_load_json_declaration(relative_path))


def _load_json_declaration(relative_path: str) -> dict[str, object]:
    resource = resources.files("sisyphus").joinpath(relative_path)
    raw = json.loads(resource.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(f"DSL declaration must be a JSON object: {relative_path}")
    return {str(key): value for key, value in raw.items()}


__all__ = ["load_execution_policy_declaration", "load_feature_change_protocol_declaration"]
