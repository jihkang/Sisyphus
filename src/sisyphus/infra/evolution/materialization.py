from __future__ import annotations

from dataclasses import asdict
import json
from pathlib import Path, PurePosixPath
import re

from ...evolution.materialization import (
    EVOLUTION_MATERIALIZATION_MODE_TASK_WORKTREE,
    EVOLUTION_MATERIALIZATION_STATUS_BASELINE_CAPTURED,
    EVOLUTION_MATERIALIZATION_STATUS_CANDIDATE_APPLIED,
    EvolutionMaterialization,
    EvolutionMaterializationError,
    ordered_target_source_paths,
    project_evolution_materialized_sources,
)
from ...shared.coerce import optional_str
from ..workspace.errors import WorkspaceFileSafetyError
from ..workspace.secure_files import SecureWorkspaceFiles


_MAX_SOURCE_BYTES = 8 * 1024 * 1024
_EVALUATION_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,199}$")


class RepositoryEvolutionMaterializer:
    def materialize(self, evaluation, *, task: dict) -> EvolutionMaterialization:
        worktree_root = Path(str(task.get("worktree_path") or "")).resolve()
        if not worktree_root.is_dir():
            raise EvolutionMaterializationError(
                f"evaluation worktree does not exist: {worktree_root}"
            )
        task_dir_value = str(task.get("task_dir") or "").strip()
        if not task_dir_value:
            raise EvolutionMaterializationError("evaluation task is missing task_dir metadata")

        try:
            task_dir = _safe_relative_path(task_dir_value, field="task_dir")
            artifact_root = task_dir / "evolution" / _artifact_slug(evaluation.evaluation_id)
            snapshot_root = artifact_root / "sources"
            files = SecureWorkspaceFiles(worktree_root)
            ordered_paths = ordered_target_source_paths(evaluation.target_ids)
            source_texts = {
                source_path: files.read_text(
                    _safe_relative_path(source_path, field="source path"),
                    max_bytes=_MAX_SOURCE_BYTES,
                )
                for source_path in ordered_paths
            }
            projection = project_evolution_materialized_sources(evaluation, source_texts)
            for source_path, final_text in projection.file_texts:
                source_relative = _safe_relative_path(source_path, field="source path")
                if evaluation.role == "candidate":
                    files.write_text_atomic(source_relative, final_text)
                files.write_text_atomic(snapshot_root / source_relative, final_text)

            status = (
                EVOLUTION_MATERIALIZATION_STATUS_CANDIDATE_APPLIED
                if evaluation.role == "candidate"
                else EVOLUTION_MATERIALIZATION_STATUS_BASELINE_CAPTURED
            )
            notes = (
                f"{evaluation.role} materialization captured {len(ordered_paths)} source files"
                if evaluation.role != "candidate"
                else f"candidate materialization applied bounded rewrites across {len(ordered_paths)} source files"
            )
            manifest_relative = artifact_root / "materialization.json"
            manifest = {
                "evaluation_id": evaluation.evaluation_id,
                "role": evaluation.role,
                "status": status,
                "mode": EVOLUTION_MATERIALIZATION_MODE_TASK_WORKTREE,
                "task_id": optional_str(task.get("id")),
                "task_dir": task_dir_value,
                "worktree_path": str(worktree_root),
                "target_ids": list(evaluation.target_ids),
                "file_paths": list(ordered_paths),
                "targets": [asdict(target) for target in projection.targets],
                "notes": notes,
            }
            files.write_text_atomic(
                manifest_relative,
                json.dumps(manifest, indent=2) + "\n",
            )
        except (OSError, UnicodeError, WorkspaceFileSafetyError) as exc:
            raise EvolutionMaterializationError(str(exc)) from exc

        return EvolutionMaterialization(
            evaluation_id=evaluation.evaluation_id,
            role=evaluation.role,
            status=status,
            mode=EVOLUTION_MATERIALIZATION_MODE_TASK_WORKTREE,
            task_id=optional_str(task.get("id")),
            task_dir=task_dir_value,
            worktree_path=str(worktree_root),
            manifest_path=manifest_relative.as_posix(),
            snapshot_root=snapshot_root.as_posix(),
            target_ids=tuple(evaluation.target_ids),
            file_paths=ordered_paths,
            targets=projection.targets,
            notes=notes,
        )


def _safe_relative_path(value: str | PurePosixPath, *, field: str) -> PurePosixPath:
    path = value if isinstance(value, PurePosixPath) else PurePosixPath(str(value))
    if path.is_absolute() or not path.parts or any(part in {"", ".", ".."} for part in path.parts):
        raise EvolutionMaterializationError(f"{field} must be a contained relative path: {value}")
    return path


def _artifact_slug(evaluation_id: str) -> str:
    normalized = str(evaluation_id).strip()
    if not _EVALUATION_ID_PATTERN.fullmatch(normalized):
        raise EvolutionMaterializationError(f"unsafe evolution evaluation id: {evaluation_id}")
    return normalized.lower().replace(":", "-")


__all__ = ["RepositoryEvolutionMaterializer"]
