from __future__ import annotations

from dataclasses import dataclass
from collections.abc import Sequence


EVOLUTION_PHASE_1 = "phase_1"
EVOLUTION_TARGET_KIND_TEXT_POLICY = "text_policy"


@dataclass(frozen=True, slots=True)
class EvolutionTarget:
    target_id: str
    phase: str
    kind: str
    title: str
    description: str
    source_paths: tuple[str, ...]
    symbol_names: tuple[str, ...]
    live_state_safe: bool = True


_REGISTERED_TARGETS: tuple[EvolutionTarget, ...] = (
    EvolutionTarget(
        target_id="execution-contract-wording",
        phase=EVOLUTION_PHASE_1,
        kind=EVOLUTION_TARGET_KIND_TEXT_POLICY,
        title="Execution Contract Wording",
        description="Execution contract text used to anchor workers to the frozen spec and conformance model.",
        source_paths=("src/sisyphus/conformance.py",),
        symbol_names=("build_execution_contract",),
    ),
    EvolutionTarget(
        target_id="mcp-tool-descriptions",
        phase=EVOLUTION_PHASE_1,
        kind=EVOLUTION_TARGET_KIND_TEXT_POLICY,
        title="MCP Tool Descriptions",
        description="Human-readable MCP tool and schema wording exposed to clients.",
        source_paths=("src/sisyphus/mcp_core.py",),
        symbol_names=("mcp_tool_definitions", "_mcp_schema_markdown"),
    ),
    EvolutionTarget(
        target_id="agent-instruction-sections",
        phase=EVOLUTION_PHASE_1,
        kind=EVOLUTION_TARGET_KIND_TEXT_POLICY,
        title="Agent Instruction Sections",
        description="Codex-facing prompt sections and instruction wording used during task execution.",
        source_paths=("src/sisyphus/codex_prompt.py",),
        symbol_names=("build_codex_prompt",),
    ),
    EvolutionTarget(
        target_id="conformance-summary-wording",
        phase=EVOLUTION_PHASE_1,
        kind=EVOLUTION_TARGET_KIND_TEXT_POLICY,
        title="Conformance Summary Wording",
        description="Human-readable summaries derived from conformance history and warnings.",
        source_paths=("src/sisyphus/conformance.py",),
        symbol_names=("_compose_summary", "_format_summary"),
    ),
    EvolutionTarget(
        target_id="review-gate-explanation-text",
        phase=EVOLUTION_PHASE_1,
        kind=EVOLUTION_TARGET_KIND_TEXT_POLICY,
        title="Review and Gate Explanation Text",
        description="Gate and audit wording surfaced during plan, spec, and verify review flows.",
        source_paths=("src/sisyphus/audit.py",),
        symbol_names=("_collect_spec_gates", "_collect_test_strategy_gates", "_gate"),
    ),
)

_TARGETS_BY_ID = {target.target_id: target for target in _REGISTERED_TARGETS}


def list_evolution_targets(*, phase: str | None = None) -> tuple[EvolutionTarget, ...]:
    if phase is None:
        return _REGISTERED_TARGETS
    return tuple(target for target in _REGISTERED_TARGETS if target.phase == phase)


def get_evolution_target(target_id: str) -> EvolutionTarget | None:
    return _TARGETS_BY_ID.get(target_id)


def resolve_evolution_targets(target_ids: Sequence[str] | None = None) -> tuple[EvolutionTarget, ...]:
    if target_ids is None:
        return _REGISTERED_TARGETS

    normalized_ids = [str(target_id).strip() for target_id in target_ids if str(target_id).strip()]
    if not normalized_ids:
        raise ValueError("evolution run requires at least one target id when an explicit selection is provided")

    requested_ids = set(normalized_ids)
    unknown_ids = sorted(requested_ids - set(_TARGETS_BY_ID))
    if unknown_ids:
        raise ValueError(f"unknown evolution target ids: {', '.join(unknown_ids)}")

    return tuple(target for target in _REGISTERED_TARGETS if target.target_id in requested_ids)
