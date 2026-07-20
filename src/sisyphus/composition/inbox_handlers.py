from __future__ import annotations

from pathlib import Path

from ..application.ports.inbox_handlers import TaskExecutionGatePort
from ..application.use_cases.conversation import ConversationEventService
from ..application.use_cases.merge_events import PullRequestMergedEventService
from ..infra.clock import SystemClock
from ..infra.config.loader import SisyphusConfig
from ..infra.daemon import (
    CallableTaskExecutionGate,
    PlanningServiceExecutionGate,
    ProviderWrapperConversationAgent,
    RepositoryChangeAdoption,
    RepositoryPromotionMerge,
)
from ..infra.documents.conversation import RepositoryConversationDocuments
from ..infra.orchestration.common_adapters import (
    EventPublisherAdapter,
    ManualInterventionAdapter,
)
from ..infra.orchestration.workflow_adapters import ProviderRunner
from ..infra.persistence.task_records import FileTaskRecordAdapter
from ..infra.providers import run_legacy_provider_wrapper
from ..templates import materialize_task_templates
from .planning import build_planning_service
from .promotion import build_promotion_service
from .task_creation import build_task_workspace_creation_service


def build_conversation_event_service(
    repo_root: Path,
    config: SisyphusConfig,
    *,
    provider_runner: ProviderRunner = run_legacy_provider_wrapper,
    gates: TaskExecutionGatePort | None = None,
) -> ConversationEventService:
    task_records = FileTaskRecordAdapter(repo_root, config)
    return ConversationEventService(
        tasks=task_records,
        creation=build_task_workspace_creation_service(
            repo_root,
            config,
            template_materializer=materialize_task_templates,
        ),
        documents=RepositoryConversationDocuments(),
        adoption=RepositoryChangeAdoption(repo_root),
        gates=gates
        or PlanningServiceExecutionGate(build_planning_service(repo_root, config)),
        agents=ProviderWrapperConversationAgent(repo_root, provider_runner),
        events=EventPublisherAdapter(repo_root, config),
        interventions=ManualInterventionAdapter(repo_root, config),
        clock=SystemClock(),
    )


def build_callable_task_execution_gate(
    repo_root: Path,
    config: SisyphusConfig,
    *,
    enforce_plan,
    enforce_spec,
) -> CallableTaskExecutionGate:
    return CallableTaskExecutionGate(
        repo_root,
        config,
        enforce_plan=enforce_plan,
        enforce_spec=enforce_spec,
    )


def build_pull_request_merged_event_service(
    repo_root: Path,
    config: SisyphusConfig,
) -> PullRequestMergedEventService:
    return PullRequestMergedEventService(
        promotions=RepositoryPromotionMerge(
            repo_root,
            config,
            build_promotion_service(repo_root, config, gh_runner=_unsupported_gh_runner),
        ),
        events=EventPublisherAdapter(repo_root, config),
    )


def _unsupported_gh_runner(*args, **kwargs):
    raise RuntimeError("GitHub CLI execution is not used while recording a merge receipt")


__all__ = [
    "build_callable_task_execution_gate",
    "build_conversation_event_service",
    "build_pull_request_merged_event_service",
]
