from __future__ import annotations

from dataclasses import dataclass

from ...domain.promotion import PromotionBaseResolution
from ..commands.promotion import ExecutePromotionCommand, RecordMergedPullRequestCommand
from ..ports.artifacts import ArtifactStorePort
from ..ports.clock import ClockPort
from ..ports.promotion import (
    PromotionTaskPort,
    PullRequestPort,
    ReopenedTaskPort,
    VersionControlPort,
)
from ..ports.review import ExternalReviewEvidencePort
from ..ports.verification import VerificationConformancePort
from ..ports.workflow import CloseoutPort, ManualInterventionPort, TaskRecord
from ..promotion_projection import DEFAULT_PROMOTION_EXECUTION_RECEIPT_PATH
from ..results.promotion import MergeReceiptResult, PromotionExecutionResult
from .promotion_execution import PromotionExecutionError, PromotionExecutionService
from .promotion_merge import MergedPromotionRecorder


@dataclass(slots=True)
class PromotionService:
    """Stable facade over the two promotion command boundaries."""

    tasks: PromotionTaskPort
    version_control: VersionControlPort
    pull_requests: PullRequestPort
    artifacts: ArtifactStorePort
    conformance: VerificationConformancePort
    closeout: CloseoutPort
    interventions: ManualInterventionPort
    reopened_tasks: ReopenedTaskPort
    clock: ClockPort
    external_reviews: ExternalReviewEvidencePort | None = None

    def execute(self, command: ExecutePromotionCommand) -> PromotionExecutionResult:
        return self._execution_service().execute(command)

    def resolve_base(
        self,
        task: TaskRecord,
        *,
        explicit_base_branch: str | None = None,
    ) -> PromotionBaseResolution:
        return self._execution_service().resolve_base(
            task,
            explicit_base_branch=explicit_base_branch,
        )

    def record_merged(self, command: RecordMergedPullRequestCommand) -> MergeReceiptResult:
        return self._merge_recorder().record(command)

    def mark_stacked_children_for_retarget(
        self,
        parent_task: TaskRecord,
        *,
        triggered_at: str,
    ) -> tuple[str, ...]:
        return self._merge_recorder().mark_stacked_children_for_retarget(
            parent_task,
            triggered_at=triggered_at,
        )

    def _execution_service(self) -> PromotionExecutionService:
        return PromotionExecutionService(
            tasks=self.tasks,
            version_control=self.version_control,
            pull_requests=self.pull_requests,
            artifacts=self.artifacts,
            conformance=self.conformance,
            external_reviews=self.external_reviews,
            clock=self.clock,
        )

    def _merge_recorder(self) -> MergedPromotionRecorder:
        return MergedPromotionRecorder(
            tasks=self.tasks,
            artifacts=self.artifacts,
            conformance=self.conformance,
            closeout=self.closeout,
            interventions=self.interventions,
            reopened_tasks=self.reopened_tasks,
            clock=self.clock,
        )


__all__ = [
    "DEFAULT_PROMOTION_EXECUTION_RECEIPT_PATH",
    "PromotionExecutionError",
    "PromotionService",
]
