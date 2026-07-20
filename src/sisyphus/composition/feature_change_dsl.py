from __future__ import annotations

from collections.abc import Iterable

from ..application.artifacts.obligations import (
    DEFAULT_FEATURE_CHANGE_PROTOCOL_DECLARATION,
    compile_feature_change_obligation as compile_obligation,
    compile_feature_change_obligations as compile_obligations,
    feature_change_obligation_specs_by_id as obligation_specs_by_id,
)
from ..application.artifacts.projection import FeatureTaskArtifactProjection
from ..domain.artifact.dsl import CompiledObligation, ObligationIntent, ObligationSpec, ProtocolSpec
from ..infra.artifacts.declarations import load_feature_change_protocol_declaration


def default_feature_change_protocol_spec() -> ProtocolSpec:
    return load_feature_change_protocol_spec_declaration()


def load_feature_change_protocol_spec_declaration(
    relative_path: str = DEFAULT_FEATURE_CHANGE_PROTOCOL_DECLARATION,
) -> ProtocolSpec:
    return load_feature_change_protocol_declaration(relative_path)


def feature_change_obligation_specs_by_id(
    protocol: ProtocolSpec | None = None,
) -> dict[str, ObligationSpec]:
    return obligation_specs_by_id(protocol or default_feature_change_protocol_spec())


def compile_feature_change_obligation(
    intent: ObligationIntent,
    projection: FeatureTaskArtifactProjection,
    *,
    protocol: ProtocolSpec | None = None,
) -> CompiledObligation:
    return compile_obligation(
        intent,
        projection,
        protocol=protocol or default_feature_change_protocol_spec(),
    )


def compile_feature_change_obligations(
    intents: Iterable[ObligationIntent],
    projection: FeatureTaskArtifactProjection,
    *,
    protocol: ProtocolSpec | None = None,
) -> tuple[CompiledObligation, ...]:
    return compile_obligations(
        intents,
        projection,
        protocol=protocol or default_feature_change_protocol_spec(),
    )


__all__ = [
    "compile_feature_change_obligation",
    "compile_feature_change_obligations",
    "default_feature_change_protocol_spec",
    "feature_change_obligation_specs_by_id",
    "load_feature_change_protocol_spec_declaration",
]
