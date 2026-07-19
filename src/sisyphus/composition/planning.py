from __future__ import annotations

from pathlib import Path

from ..application.use_cases.planning import PlanningService
from ..infra.clock import SystemClock
from ..infra.config.loader import SisyphusConfig
from ..infra.orchestration.planning_adapters import (
    DesignConformanceAdapter,
    PlanningDocumentAdapter,
    SpecValidationAdapter,
)
from ..infra.orchestration.common_adapters import FileTaskRecordAdapter, ManualInterventionAdapter


def build_planning_service(repo_root: Path, config: SisyphusConfig) -> PlanningService:
    clock = SystemClock()
    return PlanningService(
        tasks=FileTaskRecordAdapter(repo_root, config),
        documents=PlanningDocumentAdapter(repo_root, config),
        validation=SpecValidationAdapter(repo_root, config),
        design_conformance=DesignConformanceAdapter(clock),
        interventions=ManualInterventionAdapter(repo_root, config),
        clock=clock,
    )


__all__ = ["build_planning_service"]
