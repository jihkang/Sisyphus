from __future__ import annotations

from collections.abc import Sequence
import json
from pathlib import Path, PurePosixPath

from ...evolution.harness import EvolutionWorktreeCommand, EvolutionWorktreeCommandResult
from ..execution.bounded_shell import BoundedShellProcessRunner
from ..workspace.secure_files import SecureWorkspaceFiles


DEFAULT_EVOLUTION_COMMAND_TIMEOUT_SECONDS = 300.0
DEFAULT_EVOLUTION_COMMAND_OUTPUT_BYTES = 64_000


class RepositoryEvolutionCommandRunner:
    def __init__(
        self,
        *,
        timeout_seconds: float = DEFAULT_EVOLUTION_COMMAND_TIMEOUT_SECONDS,
        max_output_bytes: int = DEFAULT_EVOLUTION_COMMAND_OUTPUT_BYTES,
    ) -> None:
        self.timeout_seconds = max(float(timeout_seconds), 0.1)
        self.max_output_bytes = max(int(max_output_bytes), 256)
        self._runner = BoundedShellProcessRunner(
            timeout_seconds=self.timeout_seconds,
            max_output_bytes=self.max_output_bytes,
        )

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
            completed = self._runner.run(
                command.normalized_command,
                cwd=resolved_root,
            )
            stdout_path = execution_root / f"command-{index:03d}.stdout.txt"
            stderr_path = execution_root / f"command-{index:03d}.stderr.txt"
            files.write_text_atomic(
                stdout_path,
                _render_captured_output(
                    completed.stdout_tail,
                    truncated_bytes=completed.stdout_truncated_bytes,
                ),
            )
            files.write_text_atomic(
                stderr_path,
                _render_captured_output(
                    completed.stderr_tail,
                    truncated_bytes=completed.stderr_truncated_bytes,
                ),
            )
            output_excerpt = (
                completed.stdout_tail
                or completed.stderr_tail
                or completed.error
                or ""
            ).strip().splitlines()
            results.append(
                EvolutionWorktreeCommandResult(
                    source_task_id=command.source_task_id,
                    source=command.source,
                    original_command=command.original_command,
                    normalized_command=command.normalized_command,
                    status="passed" if completed.exit_code == 0 else "failed",
                    exit_code=completed.exit_code,
                    runtime_ms=max(1, completed.duration_ms),
                    stdout_path=stdout_path.as_posix(),
                    stderr_path=stderr_path.as_posix(),
                    output_excerpt=output_excerpt[-1][:200] if output_excerpt else None,
                    timed_out=completed.timed_out,
                    stdout_truncated_bytes=completed.stdout_truncated_bytes,
                    stderr_truncated_bytes=completed.stderr_truncated_bytes,
                    error=completed.error,
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
                    "command_timeout_seconds": self.timeout_seconds,
                    "max_output_bytes": self.max_output_bytes,
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
        "timed_out": result.timed_out,
        "stdout_truncated_bytes": result.stdout_truncated_bytes,
        "stderr_truncated_bytes": result.stderr_truncated_bytes,
        "error": result.error,
    }


def _render_captured_output(value: str, *, truncated_bytes: int) -> str:
    if truncated_bytes <= 0:
        return value
    return f"[sisyphus truncated {truncated_bytes} leading bytes]\n{value}"


__all__ = [
    "DEFAULT_EVOLUTION_COMMAND_OUTPUT_BYTES",
    "DEFAULT_EVOLUTION_COMMAND_TIMEOUT_SECONDS",
    "RepositoryEvolutionCommandRunner",
]
