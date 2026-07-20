from __future__ import annotations

import json
from pathlib import Path

from ....composition.closeout import close_task
from ....composition.external_review import record_external_review
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


def handle_review_record(
    *,
    repo_root: Path,
    config: SisyphusConfig,
    task_id: str,
    reviewer: str,
    verdict: str,
    report_path: str,
    reviewed_head_sha: str,
    finding_count: int,
    blocking_finding_count: int,
    summary: str | None,
    as_json: bool,
) -> int:
    outcome = record_external_review(
        repo_root=repo_root,
        config=config,
        task_id=task_id,
        reviewer=reviewer,
        verdict=verdict,
        report_path=report_path,
        reviewed_head_sha=reviewed_head_sha,
        finding_count=finding_count,
        blocking_finding_count=blocking_finding_count,
        summary=summary,
    )
    payload = {
        "task_id": outcome.task_id,
        "status": outcome.status,
        "provider": outcome.provider,
        "reviewer": outcome.reviewer,
        "reviewed_head_sha": outcome.reviewed_head_sha,
        "report_path": outcome.report_path,
        "report_digest": outcome.report_digest,
        "finding_count": outcome.finding_count,
        "blocking_finding_count": outcome.blocking_finding_count,
        "completed_at": outcome.completed_at,
    }
    if as_json:
        print(json.dumps(payload, sort_keys=True))
    else:
        print(f"external review {outcome.task_id}")
        print(f"status: {outcome.status}")
        print(f"provider: {outcome.provider}")
        print(f"reviewer: {outcome.reviewer}")
        print(f"reviewed_head_sha: {outcome.reviewed_head_sha}")
        print(f"report: {outcome.report_path}")
        print(f"report_digest: {outcome.report_digest}")
        print(f"findings: {outcome.finding_count}")
        print(f"blocking_findings: {outcome.blocking_finding_count}")
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
    "handle_review_record",
    "handle_verify",
]
