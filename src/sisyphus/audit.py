from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .application.use_cases.verification import TRANSIENT_GATE_SOURCES, VERIFY_GATE_CODES
from .application.verification_records import command_execution_to_record
from .composition.verification import build_verification_service
from .config import SisyphusConfig
from .shared.paths import contained_path, task_dir as resolve_task_dir


@dataclass(slots=True)
class VerifyOutcome:
    task_id: str
    status: str
    stage: str
    audit_attempts: int
    max_audit_attempts: int
    gates: list[dict]
    command_results: list[dict]
    verify_file: Path


def run_verify(repo_root: Path, config: SisyphusConfig, task_id: str) -> VerifyOutcome:
    outcome = build_verification_service(repo_root, config).verify(task_id)
    task_directory = resolve_task_dir(repo_root, config.task_dir, task_id)
    verify_file = contained_path(
        task_directory,
        outcome.verify_artifact.relative_path,
        require_relative=True,
    )
    return VerifyOutcome(
        task_id=outcome.task_id,
        status=outcome.status,
        stage=outcome.stage,
        audit_attempts=outcome.audit_attempts,
        max_audit_attempts=outcome.max_audit_attempts,
        gates=list(outcome.gates),
        command_results=[
            command_execution_to_record(result) for result in outcome.command_results
        ],
        verify_file=verify_file,
    )


__all__ = ["TRANSIENT_GATE_SOURCES", "VERIFY_GATE_CODES", "VerifyOutcome", "run_verify"]
