from __future__ import annotations

from pathlib import Path
import subprocess

from ...application.ports.clock import ClockPort
from ...application.ports.workflow import TaskRecord
from ...application.results.artifacts import ArtifactRef
from ...application.verification_records import command_execution_to_record
from ...conformance import append_conformance_log
from ...config import SisyphusConfig
from ...domain.lifecycle import ConformanceState, LifecycleAction
from ...domain.verification import CommandExecution, VerificationStatus
from ...evidence_graph import build_evidence_graph, write_evidence_graph
from ...shared.paths import contained_path, task_dir as resolve_task_dir
from ..persistence.lifecycle_mapper import LifecycleRecordMapper


class FileVerificationDocumentAdapter:
    def __init__(self, repo_root: Path, config: SisyphusConfig) -> None:
        self._repo_root = repo_root
        self._config = config

    def read(self, task_id: str, relative_path: str) -> str | None:
        path = self._path(task_id, relative_path)
        if not path.exists():
            return None
        return path.read_text(encoding="utf-8")

    def write(self, task_id: str, relative_path: str, content: str) -> ArtifactRef:
        path = self._path(task_id, relative_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return ArtifactRef(relative_path=relative_path)

    def resolve(self, task_id: str, relative_path: str) -> Path:
        return self._path(task_id, relative_path)

    def _path(self, task_id: str, relative_path: str) -> Path:
        directory = resolve_task_dir(self._repo_root, self._config.task_dir, task_id)
        return contained_path(directory, relative_path, require_relative=True)


class ShellVerificationCommandAdapter:
    def __init__(
        self,
        repo_root: Path,
        config: SisyphusConfig,
        clock: ClockPort,
    ) -> None:
        self._repo_root = repo_root
        self._config = config
        self._clock = clock

    def run(self, task_id: str, commands: tuple[str, ...]) -> tuple[CommandExecution, ...]:
        directory = resolve_task_dir(self._repo_root, self._config.task_dir, task_id)
        results: list[CommandExecution] = []
        for command in commands:
            started_at = self._clock.now()
            completed = subprocess.run(
                command,
                cwd=directory,
                shell=True,
                capture_output=True,
                text=True,
            )
            finished_at = self._clock.now()
            output_lines = (completed.stdout or completed.stderr or "").strip().splitlines()
            results.append(
                CommandExecution(
                    name=command,
                    command=command,
                    status=(
                        VerificationStatus.PASSED
                        if completed.returncode == 0
                        else VerificationStatus.FAILED
                    ),
                    exit_code=completed.returncode,
                    started_at=started_at,
                    finished_at=finished_at,
                    duration_ms=None,
                    output_excerpt=(output_lines[-1] if output_lines else "")[:200],
                )
            )
        return tuple(results)


class EvidenceGraphAdapter:
    def __init__(self, repo_root: Path, config: SisyphusConfig) -> None:
        self._repo_root = repo_root
        self._config = config

    def write(
        self,
        task_id: str,
        task: TaskRecord,
        command_results: tuple[CommandExecution, ...],
    ) -> None:
        directory = resolve_task_dir(self._repo_root, self._config.task_dir, task_id)
        records = [command_execution_to_record(result) for result in command_results]
        write_evidence_graph(directory, build_evidence_graph(task, directory, records))


class ConformanceVerificationAdapter:
    def snapshot(self, task: TaskRecord) -> ConformanceState:
        return LifecycleRecordMapper.to_domain(
            task,
            action=LifecycleAction.VERIFY,
        ).conformance

    def append(
        self,
        task: TaskRecord,
        *,
        checkpoint_type: str,
        status: str,
        summary: str,
        source: str,
        resolved: bool,
        drift: int,
    ) -> TaskRecord:
        return append_conformance_log(
            task,
            checkpoint_type=checkpoint_type,
            status=status,
            summary=summary,
            source=source,
            resolved=resolved,
            drift=drift,
        )


__all__ = [
    "ConformanceVerificationAdapter",
    "EvidenceGraphAdapter",
    "FileVerificationDocumentAdapter",
    "ShellVerificationCommandAdapter",
]
