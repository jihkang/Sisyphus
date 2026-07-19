from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from ...application.commands.promotion import RecordMergedPullRequestCommand
from ...application.results.inbox_handlers import AdoptedChanges, PromotionMergeReceipt
from ...application.use_cases.planning import PlanningService
from ...application.use_cases.promotion import PromotionService
from ...gitops import (
    copy_relative_path,
    current_branch_name,
    list_dirty_paths,
    remove_relative_path,
)
from ...shared.paths import contained_path, task_dir as resolve_task_dir
from ..config.loader import SisyphusConfig


ProviderRunner = Callable[..., int]
PlanningGate = Callable[..., tuple[bool, dict]]


class ProviderWrapperConversationAgent:
    def __init__(self, repo_root: Path, runner: ProviderRunner) -> None:
        self._repo_root = repo_root
        self._runner = runner

    def run(
        self,
        *,
        provider: str,
        task_id: str,
        agent_id: str,
        role: str,
        instruction: str | None,
        owned_paths: tuple[str, ...],
        provider_args: tuple[str, ...],
    ) -> int:
        wrapper_args = [task_id, agent_id, "--role", role]
        if instruction:
            wrapper_args.extend(["--instruction", instruction])
        for path in owned_paths:
            wrapper_args.extend(["--owned-path", path])
        for arg in provider_args:
            wrapper_args.extend(["--provider-arg", arg])
        return self._runner(provider, wrapper_args, repo_root=self._repo_root)


class CallableTaskExecutionGate:
    def __init__(
        self,
        repo_root: Path,
        config: SisyphusConfig,
        *,
        enforce_plan: PlanningGate,
        enforce_spec: PlanningGate,
    ) -> None:
        self._repo_root = repo_root
        self._config = config
        self._enforce_plan = enforce_plan
        self._enforce_spec = enforce_spec

    def enforce_plan_approved(self, task_id: str, *, action: str) -> tuple[bool, dict]:
        return self._enforce_plan(
            repo_root=self._repo_root,
            config=self._config,
            task_id=task_id,
            action=action,
        )

    def enforce_spec_frozen(self, task_id: str, *, action: str) -> tuple[bool, dict]:
        return self._enforce_spec(
            repo_root=self._repo_root,
            config=self._config,
            task_id=task_id,
            action=action,
        )


class PlanningServiceExecutionGate:
    def __init__(self, service: PlanningService) -> None:
        self._service = service

    def enforce_plan_approved(self, task_id: str, *, action: str) -> tuple[bool, dict]:
        return self._service.enforce_plan_approved(task_id, action=action)

    def enforce_spec_frozen(self, task_id: str, *, action: str) -> tuple[bool, dict]:
        return self._service.enforce_spec_frozen(task_id, action=action)


class RepositoryChangeAdoption:
    def __init__(self, repo_root: Path) -> None:
        self._repo_root = repo_root

    def apply(
        self,
        *,
        worktree_root: Path,
        requested_paths: tuple[str, ...],
    ) -> AdoptedChanges:
        source_branch = current_branch_name(self._repo_root)
        changed_paths, deleted_paths = list_dirty_paths(self._repo_root)
        changed = tuple(
            path for path in changed_paths if not is_internal_sisyphus_path(path)
        )
        deleted = tuple(
            path for path in deleted_paths if not is_internal_sisyphus_path(path)
        )
        selected_changed = _select_adopt_paths(changed, requested_paths)
        selected_deleted = _select_adopt_paths(deleted, requested_paths)

        adopted_paths: list[str] = []
        for relative_path in selected_changed:
            source_path = self._repo_root / relative_path
            if not source_path.exists():
                continue
            copy_relative_path(self._repo_root, worktree_root, relative_path)
            if relative_path not in adopted_paths:
                adopted_paths.append(relative_path)

        for relative_path in selected_deleted:
            remove_relative_path(worktree_root, relative_path)
            if relative_path not in adopted_paths:
                adopted_paths.append(relative_path)

        return AdoptedChanges(
            source_branch=source_branch,
            source_repo_root=str(self._repo_root),
            paths=tuple(adopted_paths),
            deleted_paths=selected_deleted,
        )


class RepositoryPromotionMerge:
    def __init__(
        self,
        repo_root: Path,
        config: SisyphusConfig,
        service: PromotionService,
    ) -> None:
        self._repo_root = repo_root
        self._config = config
        self._service = service

    def record(self, command: RecordMergedPullRequestCommand) -> PromotionMergeReceipt:
        result = self._service.record_merged(command)
        task_directory = resolve_task_dir(
            self._repo_root,
            self._config.task_dir,
            result.task_id,
        )
        return PromotionMergeReceipt(
            task_id=result.task_id,
            branch=result.branch,
            pr_number=result.pr_number,
            title=result.title,
            recorded_at=result.recorded_at,
            receipt_path=str(
                contained_path(
                    task_directory,
                    result.receipt.relative_path,
                    require_relative=True,
                )
            ),
            changeset_path=str(
                contained_path(
                    task_directory,
                    result.changeset.relative_path,
                    require_relative=True,
                )
            ),
            close_attempted=result.close_attempted,
            closed=result.closed,
            close_status=result.close_status,
            close_gate_codes=result.close_gate_codes,
            child_retargeted_task_ids=result.child_retargeted_task_ids,
        )


def _select_adopt_paths(
    paths: tuple[str, ...],
    requested_paths: tuple[str, ...],
) -> tuple[str, ...]:
    if not requested_paths:
        return paths
    selected: list[str] = []
    for path in paths:
        normalized = path.replace("\\", "/")
        for requested in requested_paths:
            prefix = requested.replace("\\", "/").rstrip("/")
            if normalized == prefix or normalized.startswith(f"{prefix}/"):
                selected.append(path)
                break
    return tuple(selected)


def is_internal_sisyphus_path(relative_path: str) -> bool:
    normalized = relative_path.replace("\\", "/")
    return normalized == ".planning" or normalized.startswith(".planning/")


__all__ = [
    "CallableTaskExecutionGate",
    "PlanningServiceExecutionGate",
    "ProviderWrapperConversationAgent",
    "RepositoryChangeAdoption",
    "RepositoryPromotionMerge",
    "is_internal_sisyphus_path",
]
