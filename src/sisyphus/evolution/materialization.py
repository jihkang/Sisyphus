from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from .targets import get_evolution_target


EVOLUTION_MATERIALIZATION_MODE_TASK_WORKTREE = "task_worktree"
EVOLUTION_MATERIALIZATION_STATUS_BASELINE_CAPTURED = "baseline_captured"
EVOLUTION_MATERIALIZATION_STATUS_CANDIDATE_APPLIED = "candidate_applied"
EVOLUTION_MATERIALIZATION_STATUS_FAILED = "failed"


@dataclass(frozen=True, slots=True)
class EvolutionTextMutation:
    source_path: str
    before: str
    after: str
    description: str


@dataclass(frozen=True, slots=True)
class EvolutionMaterializedTarget:
    target_id: str
    title: str
    source_paths: tuple[str, ...]
    symbol_names: tuple[str, ...]
    mutation_count: int
    detail: str


@dataclass(frozen=True, slots=True)
class EvolutionMaterialization:
    evaluation_id: str
    role: str
    status: str
    mode: str
    task_id: str | None
    task_dir: str
    worktree_path: str
    manifest_path: str
    snapshot_root: str
    target_ids: tuple[str, ...]
    file_paths: tuple[str, ...]
    targets: tuple[EvolutionMaterializedTarget, ...]
    notes: str


@dataclass(frozen=True, slots=True)
class EvolutionMaterializedSourceProjection:
    file_texts: tuple[tuple[str, str], ...]
    targets: tuple[EvolutionMaterializedTarget, ...]


class EvolutionMaterializationError(RuntimeError):
    pass


_TARGET_MUTATIONS: dict[str, tuple[EvolutionTextMutation, ...]] = {
    "execution-contract-wording": (
        EvolutionTextMutation(
            source_path="src/sisyphus/application/conformance_records.py",
            before='        "- `yellow` means a clarification or warning is pending.",\n',
            after=(
                '        "- `yellow` means unresolved drift or clarification is pending and must be resolved before continuing.",\n'
            ),
            description="tighten the yellow conformance wording",
        ),
        EvolutionTextMutation(
            source_path="src/sisyphus/application/conformance_records.py",
            before='            "- Re-anchor the implementation to the frozen spec before making changes.",\n',
            after=(
                '            "- Re-anchor to the frozen spec before editing and restate any ambiguity before continuing.",\n'
            ),
            description="make execution-rule wording more explicit",
        ),
    ),
    "mcp-tool-descriptions": (
        EvolutionTextMutation(
            source_path="src/sisyphus/mcp_core.py",
            before='            "description": "Create a repository-local task from a natural-language request.",\n',
            after=(
                '            "description": "Create an isolated repository-local task from a natural-language request and seed its task/worktree metadata.",\n'
            ),
            description="clarify the request_task tool description",
        ),
        EvolutionTextMutation(
            source_path="src/sisyphus/mcp_core.py",
            before='            "## Resources",\n',
            after='            "## Resources and Status Views",\n',
            description="make the schema markdown resource section more explicit",
        ),
    ),
    "agent-instruction-sections": (
        EvolutionTextMutation(
            source_path="src/sisyphus/codex_prompt.py",
            before='        "Keep changes aligned with the documented acceptance criteria and test strategy.",\n',
            after=(
                '        "Keep changes aligned with the frozen task docs, acceptance criteria, and declared test strategy.",\n'
            ),
            description="tighten worker instruction scope wording",
        ),
        EvolutionTextMutation(
            source_path="src/sisyphus/codex_prompt.py",
            before='        "Run relevant validation before finishing when feasible.",\n',
            after=(
                '        "Run relevant validation before finishing when feasible, and call out any remaining gaps explicitly.",\n'
            ),
            description="make validation expectations more explicit",
        ),
    ),
    "conformance-summary-wording": (
        EvolutionTextMutation(
            source_path="src/sisyphus/application/conformance_records.py",
            before='    parts: list[str] = [f"status={record.get(\'status\', CONFORMANCE_GREEN)}"]\n',
            after='    parts: list[str] = [f"conformance={record.get(\'status\', CONFORMANCE_GREEN)}"]\n',
            description="rename the summary status token to conformance",
        ),
        EvolutionTextMutation(
            source_path="src/sisyphus/application/conformance_records.py",
            before='    return " | ".join(field for field in fields if field)\n',
            after='    return " / ".join(field for field in fields if field)\n',
            description="normalize event-summary separators",
        ),
    ),
    "review-gate-explanation-text": (
        EvolutionTextMutation(
            source_path="src/sisyphus/application/use_cases/verification.py",
            before=(
                '                        "feature task requires filled acceptance criteria",\n'
            ),
            after=(
                '                        "feature task must define explicit acceptance criteria before review can pass",\n'
            ),
            description="make the acceptance-criteria gate actionable",
        ),
        EvolutionTextMutation(
            source_path="src/sisyphus/application/use_cases/verification.py",
            before=(
                '                    "normal, edge, exception cases and verification methods must be defined",\n'
            ),
            after=(
                '                    "define normal, edge, and exception cases plus verification methods before review can pass",\n'
            ),
            description="make the test-strategy gate actionable",
        ),
    ),
}


def ordered_target_source_paths(target_ids: Sequence[str]) -> tuple[str, ...]:
    ordered: list[str] = []
    seen: set[str] = set()
    for target_id in target_ids:
        target = get_evolution_target(target_id)
        if target is None:
            raise EvolutionMaterializationError(f"unknown evolution target id: {target_id}")
        for source_path in target.source_paths:
            if source_path in seen:
                continue
            seen.add(source_path)
            ordered.append(source_path)
    return tuple(ordered)


def project_evolution_materialized_sources(
    evaluation,
    source_texts: Mapping[str, str],
) -> EvolutionMaterializedSourceProjection:
    ordered_paths = ordered_target_source_paths(evaluation.target_ids)
    missing_paths = [path for path in ordered_paths if path not in source_texts]
    if missing_paths:
        raise EvolutionMaterializationError(
            "materialization source text is unavailable: " + ", ".join(missing_paths)
        )
    file_texts = {path: str(source_texts[path]) for path in ordered_paths}
    target_results: list[EvolutionMaterializedTarget] = []
    for target_id in evaluation.target_ids:
        target = get_evolution_target(target_id)
        if target is None:
            raise EvolutionMaterializationError(f"unknown evolution target id: {target_id}")
        mutation_count = 0
        if evaluation.role == "candidate":
            mutation_count = _apply_candidate_mutations(target_id, file_texts)
            detail = (
                f"applied {mutation_count} bounded text/policy rewrites for candidate target `{target_id}`"
            )
        else:
            detail = f"captured baseline source snapshot for target `{target_id}` without source rewrites"
        target_results.append(
            EvolutionMaterializedTarget(
                target_id=target.target_id,
                title=target.title,
                source_paths=target.source_paths,
                symbol_names=target.symbol_names,
                mutation_count=mutation_count,
                detail=detail,
            )
        )
    return EvolutionMaterializedSourceProjection(
        file_texts=tuple((path, file_texts[path]) for path in ordered_paths),
        targets=tuple(target_results),
    )


def _apply_candidate_mutations(target_id: str, file_texts: dict[str, str]) -> int:
    mutations = _TARGET_MUTATIONS.get(target_id)
    if not mutations:
        raise EvolutionMaterializationError(f"no bounded mutations are registered for target `{target_id}`")

    applied = 0
    for mutation in mutations:
        current_text = file_texts.get(mutation.source_path)
        if current_text is None:
            raise EvolutionMaterializationError(
                f"materialization source file is unavailable for target `{target_id}`: {mutation.source_path}"
            )
        if mutation.before in current_text:
            file_texts[mutation.source_path] = current_text.replace(mutation.before, mutation.after, 1)
            applied += 1
            continue
        if mutation.after in current_text:
            applied += 1
            continue
        raise EvolutionMaterializationError(
            f"bounded mutation anchor missing for target `{target_id}` in {mutation.source_path}: {mutation.description}"
        )
    return applied
