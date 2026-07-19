from __future__ import annotations

from pathlib import Path
from typing import Protocol

from ...application.ports.workflow import (
    CloseoutResult,
    ConformanceCheck,
    ProviderRequest,
    TaskRecord,
    VerificationResult,
    WorkflowEvent,
)
from ...application.use_cases.planning import PlanningService
from ...audit import run_verify
from ...bus import build_event_publisher
from ...closeout import run_close
from ...config import SisyphusConfig
from ...conformance import (
    append_conformance_log_markdown,
    build_execution_contract,
    run_post_execution_conformance_check,
    run_pre_execution_conformance_check,
    summarize_task_conformance,
)
from ...events import new_event_envelope
from ...obligation_runtime import converge_feature_change_obligations
from ...shared.paths import task_dir as resolve_task_dir


class ProviderRunner(Protocol):
    def __call__(
        self,
        provider: str,
        argv: list[str],
        *,
        repo_root: Path | None = None,
    ) -> int: ...


class PlanningWorkflowAdapter:
    def __init__(self, service: PlanningService) -> None:
        self._service = service

    def freeze_spec(self, task_id: str) -> None:
        self._service.freeze_spec(
            task_id,
            reviewer="workflow-daemon",
            notes="automatic spec freeze after plan approval",
        )

    def generate_subtasks(self, task_id: str) -> None:
        self._service.generate_subtasks(task_id)


class FeatureObligationAdapter:
    def __init__(self, repo_root: Path, config: SisyphusConfig) -> None:
        self._repo_root = repo_root
        self._config = config

    def converge(self, task_id: str) -> bool:
        return converge_feature_change_obligations(
            repo_root=self._repo_root,
            config=self._config,
            task_id=task_id,
        ).progressed


class ConformanceAdapter:
    def __init__(self, repo_root: Path, config: SisyphusConfig) -> None:
        self._repo_root = repo_root
        self._config = config

    def pre_execution(
        self,
        task: TaskRecord,
        *,
        subtask_id: str,
        source: str,
    ) -> ConformanceCheck:
        status, summary = run_pre_execution_conformance_check(
            task,
            subtask_id=subtask_id,
            source=source,
        )
        return ConformanceCheck(status=status, summary=summary)

    def post_execution(
        self,
        task: TaskRecord,
        *,
        subtask_id: str,
        exit_code: int,
        source: str,
    ) -> ConformanceCheck:
        status, summary = run_post_execution_conformance_check(
            task,
            subtask_id=subtask_id,
            exit_code=exit_code,
            source=source,
        )
        return ConformanceCheck(status=status, summary=summary)

    def execution_contract(self, task: TaskRecord, subtask: dict[str, object]) -> str:
        return build_execution_contract(task, subtask)

    def write_log(self, task: TaskRecord) -> None:
        task_id = str(task.get("id") or "")
        directory = resolve_task_dir(self._repo_root, self._config.task_dir, task_id)
        append_conformance_log_markdown(task, directory)

    def status(self, task: TaskRecord) -> str:
        return str(summarize_task_conformance(task).get("status") or "green")


class ProviderAdapter:
    def __init__(self, repo_root: Path, runner: ProviderRunner) -> None:
        self._repo_root = repo_root
        self._runner = runner

    def run(self, request: ProviderRequest) -> int:
        return self._runner(
            request.provider,
            [
                request.task_id,
                request.agent_id,
                "--role",
                request.role,
                "--instruction",
                request.instruction,
            ],
            repo_root=self._repo_root,
        )


class VerificationAdapter:
    def __init__(self, repo_root: Path, config: SisyphusConfig) -> None:
        self._repo_root = repo_root
        self._config = config

    def verify(self, task_id: str) -> VerificationResult:
        outcome = run_verify(
            repo_root=self._repo_root,
            config=self._config,
            task_id=task_id,
        )
        return VerificationResult(gates=tuple(outcome.gates))


class CloseoutAdapter:
    def __init__(self, repo_root: Path, config: SisyphusConfig) -> None:
        self._repo_root = repo_root
        self._config = config

    def close(self, task_id: str, *, allow_dirty: bool) -> CloseoutResult:
        outcome = run_close(
            repo_root=self._repo_root,
            config=self._config,
            task_id=task_id,
            allow_dirty=allow_dirty,
        )
        return CloseoutResult(closed=outcome.closed)


class EventPublisherAdapter:
    def __init__(self, repo_root: Path, config: SisyphusConfig) -> None:
        self._publisher = build_event_publisher(repo_root, config)

    def publish(self, event: WorkflowEvent) -> None:
        self._publisher.publish(
            new_event_envelope(
                event.event_type,
                source=event.source,
                data=event.data,
            )
        )


__all__ = [
    "CloseoutAdapter",
    "ConformanceAdapter",
    "EventPublisherAdapter",
    "FeatureObligationAdapter",
    "PlanningWorkflowAdapter",
    "ProviderAdapter",
    "ProviderRunner",
    "VerificationAdapter",
]
