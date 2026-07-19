from __future__ import annotations

from pathlib import Path

from ..application.commands.promotion import ExecutePromotionCommand
from ..application.results.repository_promotion import RepositoryPromotionExecutionResult
from ..infra.config.loader import SisyphusConfig, load_config
from ..infra.promotion import GhRunner, run_gh
from ..shared.paths import contained_path, task_dir as resolve_task_dir
from .promotion import build_promotion_service


def execute_promotion(
    repo_root: Path,
    *,
    config: SisyphusConfig | None = None,
    task_id: str,
    remote_name: str = "origin",
    repo_full_name: str | None = None,
    title: str | None = None,
    body: str | None = None,
    commit_message: str | None = None,
    base_branch: str | None = None,
    head_branch: str | None = None,
    draft: bool = True,
    gh_runner: GhRunner = run_gh,
) -> RepositoryPromotionExecutionResult:
    effective_config = config or load_config(repo_root)
    try:
        outcome = build_promotion_service(
            repo_root,
            effective_config,
            gh_runner=gh_runner,
        ).execute(
            ExecutePromotionCommand(
                task_id=task_id,
                remote_name=remote_name,
                repo_full_name=repo_full_name,
                title=title,
                body=body,
                commit_message=commit_message,
                base_branch=base_branch,
                head_branch=head_branch,
                draft=draft,
            )
        )
    except Exception as exc:
        return RepositoryPromotionExecutionResult(
            task_id=task_id,
            status=None,
            branch=None,
            base_branch=None,
            head_branch=None,
            commit_sha=None,
            pr_number=None,
            pr_url=None,
            receipt_path=None,
            error=str(exc),
        )

    task_directory = resolve_task_dir(repo_root, effective_config.task_dir, outcome.task_id)
    return RepositoryPromotionExecutionResult(
        task_id=outcome.task_id,
        status=outcome.status,
        branch=outcome.branch,
        base_branch=outcome.base_branch,
        head_branch=outcome.head_branch,
        commit_sha=outcome.commit_sha,
        pr_number=outcome.pr_number,
        pr_url=outcome.pr_url,
        receipt_path=contained_path(
            task_directory,
            outcome.receipt.relative_path,
            require_relative=True,
        ),
        error=None,
    )


__all__ = ["execute_promotion"]
