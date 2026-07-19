from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from ...conformance import default_task_conformance
from ...design import default_task_design
from ...gitops import branch_name, worktree_path
from ...promotion_state import default_task_promotion
from ...shared.clock import utc_now
from ...shared.paths import task_dir
from ...domain.task.models import default_task_docs
from ..config.loader import SisyphusConfig


def task_id_for(task_type: str, slug: str, now: datetime | None = None) -> str:
    current = now or datetime.now(timezone.utc)
    return f"TF-{current:%Y%m%d}-{task_type}-{slug}"


def build_task_record(
    repo_root: Path,
    config: SisyphusConfig,
    task_type: str,
    slug: str,
    *,
    spec_validation_required: bool = False,
) -> dict:
    task_id = task_id_for(task_type=task_type, slug=slug)
    branch = branch_name(
        task_type=task_type,
        slug=slug,
        feature_prefix=config.branch_prefix_feature,
        issue_prefix=config.branch_prefix_issue,
    )
    task_path = task_dir(repo_root, config.task_dir, task_id)

    verify_profile = task_type if task_type in config.verify else "default"
    verify_keys = config.verify.get(verify_profile, [])
    verify_commands = [config.commands[name] for name in verify_keys if name in config.commands]

    docs = default_task_docs(task_type)

    return {
        "id": task_id,
        "type": task_type,
        "slug": slug,
        "status": "open",
        "stage": "spec",
        "plan_status": "pending_review",
        "plan_reviewed_at": None,
        "plan_reviewed_by": None,
        "plan_review_notes": None,
        "plan_review_round": 0,
        "max_plan_review_rounds": 3,
        "plan_review_history": [],
        "workflow_phase": "plan_in_review",
        "spec_status": "draft",
        "spec_frozen_at": None,
        "spec_reviewed_by": None,
        "spec_review_notes": None,
        "audit_attempts": 0,
        "max_audit_attempts": 10,
        "created_at": utc_now(),
        "updated_at": utc_now(),
        "closed_at": None,
        "repo_root": str(repo_root.resolve()),
        "task_dir": str(task_path.relative_to(repo_root)),
        "worktree_path": str(worktree_path(repo_root, config.worktree_root, task_id)),
        "branch": branch,
        "base_branch": config.base_branch,
        "verify_profile": verify_profile,
        "verify_commands": verify_commands,
        "verify_status": "not_run",
        "last_verified_at": None,
        "last_verify_results": [],
        "test_strategy": {
            "normal_cases": [],
            "edge_cases": [],
            "exception_cases": [],
            "verification_methods": [],
            "external_llm": {
                "required": False,
                "provider": None,
                "purpose": None,
                "trigger": None,
                "status": "not_needed",
            },
        },
        "design": default_task_design(),
        "promotion": default_task_promotion(),
        "gates": [],
        "subtasks": [],
        "conformance": default_task_conformance(),
        "docs": docs,
        "meta": {
            "sequence": None,
            "close_override_used": False,
            "spec_validation_required": spec_validation_required,
        },
    }


__all__ = [
    "build_task_record",
    "task_id_for",
]
