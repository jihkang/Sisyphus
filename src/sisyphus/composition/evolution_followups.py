from __future__ import annotations

from pathlib import Path

from ..application.commands.evolution import RequestEvolutionFollowupCommand
from ..application.commands.inbox import QueueConversationCommand
from ..application.results.repository_requests import TaskRequestResult
from ..application.use_cases.repository_requests import RepositoryRequestService
from ..evolution.bridge import (
    EvolutionBridgedFollowupTask,
    bridge_evolution_followup_request_from_ports,
    get_legacy_request_task,
)
from ..evolution.handoff import EvolutionFollowupRequest
from ..infra.config.loader import SisyphusConfig, load_config
from ..infra.evolution import RepositoryEvolutionEvents
from .repository_requests import build_repository_request_service


class ReviewGatedEvolutionFollowupRequester:
    def __init__(self, requests: RepositoryRequestService) -> None:
        self._requests = requests

    def request(self, command: RequestEvolutionFollowupCommand) -> TaskRequestResult:
        return self._requests.request_task(
            QueueConversationCommand(
                message=command.message,
                title=command.title,
                task_type=command.task_type,
                slug=command.slug,
                instruction=command.instruction,
                owned_paths=command.owned_paths,
                source_context=command.source_context,
                auto_run=False,
            )
        )


class LegacyEvolutionFollowupRequester:
    def __init__(self, repo_root: Path, config: SisyphusConfig, request_task) -> None:
        self._repo_root = repo_root
        self._config = config
        self._request_task = request_task

    def request(self, command: RequestEvolutionFollowupCommand) -> TaskRequestResult:
        return self._request_task(
            repo_root=self._repo_root,
            config=self._config,
            message=command.message,
            title=command.title,
            task_type=command.task_type,
            slug=command.slug,
            instruction=command.instruction,
            owned_paths=list(command.owned_paths),
            source_context=command.source_context,
            auto_run=False,
        )


def bridge_evolution_followup_request(
    repo_root: Path,
    followup_request: EvolutionFollowupRequest,
    *,
    config: SisyphusConfig | None = None,
    slug: str | None = None,
) -> EvolutionBridgedFollowupTask:
    resolved_repo_root = repo_root.resolve()
    resolved_config = config or load_config(resolved_repo_root)
    legacy_hook = get_legacy_request_task()
    requester = (
        LegacyEvolutionFollowupRequester(resolved_repo_root, resolved_config, legacy_hook)
        if callable(legacy_hook)
        else ReviewGatedEvolutionFollowupRequester(
            build_repository_request_service(resolved_repo_root, resolved_config)
        )
    )
    return bridge_evolution_followup_request_from_ports(
        requester,
        RepositoryEvolutionEvents(resolved_repo_root, resolved_config),
        followup_request,
        slug=slug,
    )


__all__ = [
    "LegacyEvolutionFollowupRequester",
    "ReviewGatedEvolutionFollowupRequester",
    "bridge_evolution_followup_request",
]
