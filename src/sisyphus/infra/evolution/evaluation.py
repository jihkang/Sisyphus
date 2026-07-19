from __future__ import annotations

from collections.abc import Sequence
import json
from pathlib import Path, PurePosixPath
import subprocess
from time import perf_counter

from ...evolution.harness import EvolutionWorktreeCommand, EvolutionWorktreeCommandResult
from ..workspace.secure_files import SecureWorkspaceFiles


class RepositoryEvolutionCommandRunner:
    def run(
        self,
        *,
        commands: Sequence[EvolutionWorktreeCommand],
        worktree_root: Path,
        artifact_root: Path,
        recorded_at: str,
    ) -> tuple[str, tuple[EvolutionWorktreeCommandResult, ...]]:
        resolved_root = worktree_root.resolve()
        if not resolved_root.is_dir():
            raise FileNotFoundError(f"evaluation worktree does not exist: {resolved_root}")
        artifact_relative = _contained_relative_path(
            artifact_root,
            root=resolved_root,
            field="evaluation artifact root",
        )
        execution_root = artifact_relative / "execution"
        files = SecureWorkspaceFiles(resolved_root)
        results: list[EvolutionWorktreeCommandResult] = []
        for index, command in enumerate(commands, start=1):
            started = perf_counter()
            completed = subprocess.run(
                command.normalized_command,
                cwd=resolved_root,
                shell=True,
                capture_output=True,
                text=True,
                check=False,
            )
            runtime_ms = _elapsed_ms(started)
            stdout_path = execution_root / f"command-{index:03d}.stdout.txt"
            stderr_path = execution_root / f"command-{index:03d}.stderr.txt"
            files.write_text_atomic(stdout_path, completed.stdout or "")
            files.write_text_atomic(stderr_path, completed.stderr or "")
            output_excerpt = (completed.stdout or completed.stderr or "").strip().splitlines()
            results.append(
                EvolutionWorktreeCommandResult(
                    source_task_id=command.source_task_id,
                    source=command.source,
                    original_command=command.original_command,
                    normalized_command=command.normalized_command,
                    status="passed" if completed.returncode == 0 else "failed",
                    exit_code=completed.returncode,
                    runtime_ms=runtime_ms,
                    stdout_path=stdout_path.as_posix(),
                    stderr_path=stderr_path.as_posix(),
                    output_excerpt=output_excerpt[-1][:200] if output_excerpt else None,
                )
            )

        receipt_path = execution_root / "execution_receipt.json"
        files.write_text_atomic(
            receipt_path,
            json.dumps(
                {
                    "command_count": len(results),
                    "passed_command_count": sum(
                        1 for result in results if result.status == "passed"
                    ),
                    "results": [_result_payload(result) for result in results],
                    "recorded_at": recorded_at,
                },
                indent=2,
            )
            + "\n",
        )
        return receipt_path.as_posix(), tuple(results)


def _contained_relative_path(path: Path, *, root: Path, field: str) -> PurePosixPath:
    try:
        relative = path.resolve(strict=False).relative_to(root.resolve())
    except ValueError as exc:
        raise ValueError(f"{field} escapes the evaluation worktree: {path}") from exc
    normalized = PurePosixPath(relative.as_posix())
    if not normalized.parts or any(part in {"", ".", ".."} for part in normalized.parts):
        raise ValueError(f"{field} is not a contained relative path: {path}")
    return normalized


def _result_payload(result: EvolutionWorktreeCommandResult) -> dict[str, object]:
    return {
        "source_task_id": result.source_task_id,
        "source": result.source,
        "original_command": result.original_command,
        "normalized_command": result.normalized_command,
        "status": result.status,
        "exit_code": result.exit_code,
        "runtime_ms": result.runtime_ms,
        "stdout_path": result.stdout_path,
        "stderr_path": result.stderr_path,
        "output_excerpt": result.output_excerpt,
    }


def _elapsed_ms(started: float) -> int:
    return max(1, int((perf_counter() - started) * 1000))


__all__ = ["RepositoryEvolutionCommandRunner"]
