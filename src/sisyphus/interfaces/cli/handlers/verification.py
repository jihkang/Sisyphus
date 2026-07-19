from __future__ import annotations

from pathlib import Path

from ....composition.closeout import close_task
from ....composition.verification import (
    resolve_verification_artifact_path,
    verify_task,
)
from ....config import SisyphusConfig


def handle_verify(*, repo_root: Path, config: SisyphusConfig, task_id: str) -> int:
    outcome = verify_task(repo_root=repo_root, config=config, task_id=task_id)
    verify_file = resolve_verification_artifact_path(
        repo_root,
        config,
        task_id,
        outcome.verify_artifact.relative_path,
    )
    print(f"verified {outcome.task_id}")
    print(f"status: {outcome.status}")
    print(f"audit_attempts: {outcome.audit_attempts}/{outcome.max_audit_attempts}")
    print(f"verify_file: {verify_file}")
    if outcome.gates:
        print("gates:")
        for gate in outcome.gates:
            print(f"- {gate['code']}: {gate['message']}")
        return 1
    print("gates: none")
    return 0


def handle_close(*, repo_root: Path, config: SisyphusConfig, task_id: str, allow_dirty: bool) -> int:
    outcome = close_task(
        repo_root=repo_root,
        config=config,
        task_id=task_id,
        allow_dirty=allow_dirty,
    )
    print(f"close {outcome.task_id}")
    print(f"status: {outcome.status}")
    print(f"closed: {'yes' if outcome.closed else 'no'}")
    if outcome.gates:
        print("gates:")
        for gate in outcome.gates:
            print(f"- {gate['code']}: {gate['message']}")
        return 1
    print("gates: none")
    return 0


__all__ = [
    "handle_close",
    "handle_verify",
]
