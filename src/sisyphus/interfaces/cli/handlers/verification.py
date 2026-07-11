from __future__ import annotations

from pathlib import Path

from ....audit import run_verify
from ....closeout import run_close
from ....config import SisyphusConfig


def handle_verify(*, repo_root: Path, config: SisyphusConfig, task_id: str) -> int:
    outcome = run_verify(repo_root=repo_root, config=config, task_id=task_id)
    print(f"verified {outcome.task_id}")
    print(f"status: {outcome.status}")
    print(f"audit_attempts: {outcome.audit_attempts}/{outcome.max_audit_attempts}")
    print(f"verify_file: {outcome.verify_file}")
    if outcome.gates:
        print("gates:")
        for gate in outcome.gates:
            print(f"- {gate['code']}: {gate['message']}")
        return 1
    print("gates: none")
    return 0


def handle_close(*, repo_root: Path, config: SisyphusConfig, task_id: str, allow_dirty: bool) -> int:
    outcome = run_close(repo_root=repo_root, config=config, task_id=task_id, allow_dirty=allow_dirty)
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
