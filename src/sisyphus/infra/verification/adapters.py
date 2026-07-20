from __future__ import annotations

from pathlib import Path
import uuid

from ...application.ports.clock import ClockPort
from ...application.ports.workflow import TaskRecord
from ...application.results.artifacts import ArtifactRef
from ...application.verification_evidence import (
    DEFAULT_EVIDENCE_GRAPH_PATH,
    build_verification_evidence_graph,
)
from ...application.verification_records import command_execution_to_record
from ...domain.task.conformance import append_conformance_entry
from ...domain.lifecycle import ConformanceState, LifecycleAction
from ...domain.verification import CommandExecution, VerificationStatus
from ...shared.paths import contained_path, task_dir as resolve_task_dir
from ..artifacts.store import RepositoryArtifactStore
from ..config.loader import SisyphusConfig
from ..persistence.lifecycle_mapper import LifecycleRecordMapper
from .shell import BoundedShellCommandRunner


class FileVerificationDocumentAdapter:
    def __init__(self, repo_root: Path, config: SisyphusConfig) -> None:
        self._repo_root = repo_root
        self._config = config
        self._artifacts = RepositoryArtifactStore(repo_root, config)

    def read(self, task_id: str, relative_path: str) -> str | None:
        path = self._path(task_id, relative_path)
        if not path.exists():
            return None
        return path.read_text(encoding="utf-8")

    def write(self, task_id: str, relative_path: str, content: str) -> ArtifactRef:
        return self._artifacts.write_text(task_id, relative_path, content)

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
        *,
        timeout_seconds: float = 300.0,
        max_output_bytes: int = 64_000,
        runner: BoundedShellCommandRunner | None = None,
    ) -> None:
        self._repo_root = repo_root
        self._config = config
        self._clock = clock
        self._runner = runner or BoundedShellCommandRunner(
            timeout_seconds=timeout_seconds,
            max_output_bytes=max_output_bytes,
        )

    def run(self, task_id: str, commands: tuple[str, ...]) -> tuple[CommandExecution, ...]:
        directory = resolve_task_dir(self._repo_root, self._config.task_dir, task_id)
        results: list[CommandExecution] = []
        for command in commands:
            started_at = self._clock.now()
            parse_error: str | None = None
            try:
                completed = self._runner.run(command, cwd=directory)
            except (TypeError, ValueError) as exc:
                completed = None
                parse_error = str(exc)
            finished_at = self._clock.now()
            if completed is None:
                exit_code = 2
                duration_ms = 0
                output_lines = [parse_error or "invalid verification command"]
            else:
                exit_code = completed.exit_code
                duration_ms = completed.duration_ms
                output_lines = (completed.error or completed.output_tail).strip().splitlines()
            results.append(
                CommandExecution(
                    name=command,
                    command=command,
                    status=(
                        VerificationStatus.PASSED
                        if exit_code == 0
                        else VerificationStatus.FAILED
                    ),
                    exit_code=exit_code,
                    started_at=started_at,
                    finished_at=finished_at,
                    duration_ms=duration_ms,
                    output_excerpt=(output_lines[-1] if output_lines else "")[:200],
                )
            )
        return tuple(results)


class RepositoryVerificationEvidenceAdapter:
    def __init__(
        self,
        repo_root: Path,
        config: SisyphusConfig,
        clock: ClockPort,
    ) -> None:
        self._repo_root = repo_root
        self._config = config
        self._clock = clock
        self._artifacts = RepositoryArtifactStore(repo_root, config)

    def write(
        self,
        task_id: str,
        task: TaskRecord,
        command_results: tuple[CommandExecution, ...],
    ) -> None:
        records = [command_execution_to_record(result) for result in command_results]
        docs = task.get("docs")
        changeset_path = str(docs.get("changeset") or "") if isinstance(docs, dict) else ""
        changeset_present = bool(
            changeset_path and self._artifacts.resolve(task_id, changeset_path).is_file()
        )
        conformance = LifecycleRecordMapper.to_domain(
            task,
            action=LifecycleAction.VERIFY,
        ).conformance
        graph = build_verification_evidence_graph(
            task,
            records,
            generated_at=self._clock.now(),
            conformance_status=conformance.status,
            changeset_path=changeset_path or None,
            changeset_present=changeset_present,
        )
        self._artifacts.write_json(task_id, DEFAULT_EVIDENCE_GRAPH_PATH, graph)


EvidenceGraphAdapter = RepositoryVerificationEvidenceAdapter


class ConformanceVerificationAdapter:
    def __init__(self, clock: ClockPort) -> None:
        self._clock = clock

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
        return append_conformance_entry(
            task,
            checkpoint_type=checkpoint_type,
            status=status,
            timestamp=self._clock.now(),
            task_event_id=uuid.uuid4().hex,
            summary=summary,
            source=source,
            resolved=resolved,
            drift=drift,
        )


__all__ = [
    "ConformanceVerificationAdapter",
    "EvidenceGraphAdapter",
    "FileVerificationDocumentAdapter",
    "RepositoryVerificationEvidenceAdapter",
    "ShellVerificationCommandAdapter",
]
