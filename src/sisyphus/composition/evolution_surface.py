from __future__ import annotations

from collections.abc import Sequence
import json
from pathlib import Path

from ..application.evolution_runs import EVOLUTION_RUN_ARTIFACT_NAMES
from ..evolution.orchestrator import EvolutionRunExecutionError
from ..evolution.presentation import (
    EvolutionExecutionSurfaceResult,
    EvolutionRunArtifacts,
    evolution_run_uri,
    render_evolution_run_overview,
)
from ..infra.config.loader import SisyphusConfig
from ..infra.evolution import RepositoryEvolutionRunStore
from .evolution_runs import execute_evolution_run


def load_evolution_run_artifacts(repo_root: Path, run_id: str) -> EvolutionRunArtifacts:
    resolved_root = repo_root.resolve()
    if not resolved_root.exists():
        raise FileNotFoundError(f"repository root does not exist: {resolved_root}")
    store = RepositoryEvolutionRunStore(resolved_root)
    if not store.run_exists(run_id):
        raise FileNotFoundError(f"evolution run not found: {run_id}")
    run_payload = store.read_json(run_id, "run.json")
    if run_payload is None:
        raise FileNotFoundError(f"evolution run is missing run.json: {run_id}")
    return EvolutionRunArtifacts(
        repo_root=str(resolved_root),
        run_id=run_id,
        artifact_dir=str(store.artifact_dir(run_id)),
        run=run_payload,
        dataset=store.read_json(run_id, "dataset.json"),
        harness_plan=store.read_json(run_id, "harness_plan.json"),
        constraints=store.read_json(run_id, "constraints.json"),
        fitness=store.read_json(run_id, "fitness.json"),
        report_markdown=store.read_text(run_id, "report.md"),
        failure=store.read_json(run_id, "failure.json"),
        available_artifact_names=tuple(
            name for name in EVOLUTION_RUN_ARTIFACT_NAMES if store.artifact_exists(run_id, name)
        ),
    )


def execute_evolution_surface(
    repo_root: Path,
    *,
    target_ids: Sequence[str] | None = None,
    task_ids: Sequence[str] | None = None,
    max_events: int = 50,
    run_id: str | None = None,
    config: SisyphusConfig | None = None,
) -> EvolutionExecutionSurfaceResult:
    resolved_root = repo_root.resolve()
    try:
        executed = execute_evolution_run(
            resolved_root,
            target_ids=target_ids,
            task_ids=task_ids,
            max_events=max_events,
            run_id=run_id,
            config=config,
        )
    except EvolutionRunExecutionError as exc:
        return _failure_result(
            resolved_root,
            run_id=exc.result.run.run_id,
            artifact_dir=exc.result.artifact_dir,
            final_stage=exc.result.final_stage,
            error=exc.result.failure.message,
            error_type=exc.result.failure.error_type,
            failure_stage=exc.result.failure.stage,
        )
    except Exception as exc:
        artifact_dir = _existing_artifact_dir(resolved_root, run_id)
        return _failure_result(
            resolved_root,
            run_id=run_id,
            artifact_dir=artifact_dir,
            final_stage="failed",
            error=str(exc),
            error_type=type(exc).__name__,
            failure_stage=None,
        )

    artifacts = load_evolution_run_artifacts(resolved_root, executed.run.run_id)
    return EvolutionExecutionSurfaceResult(
        ok=True,
        run_id=executed.run.run_id,
        artifact_dir=executed.artifact_dir,
        resource_uri=evolution_run_uri(executed.run.run_id, "run"),
        final_stage=executed.final_stage,
        content=render_evolution_run_overview(artifacts),
    )


def _failure_result(
    repo_root: Path,
    *,
    run_id: str | None,
    artifact_dir: str | None,
    final_stage: str | None,
    error: str,
    error_type: str,
    failure_stage: str | None,
) -> EvolutionExecutionSurfaceResult:
    content = _failure_content(
        repo_root,
        run_id=run_id,
        artifact_dir=artifact_dir,
        final_stage=final_stage,
        error=error,
        error_type=error_type,
        failure_stage=failure_stage,
    )
    return EvolutionExecutionSurfaceResult(
        ok=False,
        run_id=run_id,
        artifact_dir=artifact_dir,
        resource_uri=evolution_run_uri(run_id, "run") if run_id else None,
        final_stage=final_stage,
        content=content,
        error=error,
        error_type=error_type,
        failure_stage=failure_stage,
    )


def _failure_content(
    repo_root: Path,
    *,
    run_id: str | None,
    artifact_dir: str | None,
    final_stage: str | None,
    error: str,
    error_type: str,
    failure_stage: str | None,
) -> str:
    if run_id:
        try:
            return render_evolution_run_overview(load_evolution_run_artifacts(repo_root, run_id))
        except (FileNotFoundError, ValueError, OSError, UnicodeError, json.JSONDecodeError):
            pass
    lines = ["evolution execute failed"]
    if run_id:
        lines.append(f"run_id: {run_id}")
    if artifact_dir:
        lines.append(f"artifact_dir: {artifact_dir}")
    if final_stage:
        lines.append(f"final_stage: {final_stage}")
    if failure_stage:
        lines.append(f"failure_stage: {failure_stage}")
    lines.append(f"error_type: {error_type}")
    lines.append(f"error: {error}")
    return "\n".join(lines) + "\n"


def _existing_artifact_dir(repo_root: Path, run_id: str | None) -> str | None:
    if not run_id:
        return None
    try:
        store = RepositoryEvolutionRunStore(repo_root)
        return str(store.artifact_dir(run_id)) if store.run_exists(run_id) else None
    except ValueError:
        return None


__all__ = ["execute_evolution_surface", "load_evolution_run_artifacts"]
