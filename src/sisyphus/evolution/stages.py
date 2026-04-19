from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, TypeAlias


EVOLUTION_RUN_STAGE_PLANNED = "planned"
EVOLUTION_RUN_STAGE_DATASET_BUILT = "dataset_built"
EVOLUTION_RUN_STAGE_HARNESS_PLANNED = "harness_planned"
EVOLUTION_RUN_STAGE_CONSTRAINTS_EVALUATED = "constraints_evaluated"
EVOLUTION_RUN_STAGE_FITNESS_EVALUATED = "fitness_evaluated"
EVOLUTION_RUN_STAGE_REPORT_BUILT = "report_built"
EVOLUTION_RUN_STAGE_FAILED = "failed"

EVOLUTION_RUN_STAGE_READY_FOR_REVIEW = "ready_for_review"
EVOLUTION_RUN_STAGE_FOLLOWUP_REQUESTED = "followup_requested"
EVOLUTION_RUN_STAGE_PROMOTED = "promoted"
EVOLUTION_RUN_STAGE_INVALIDATED = "invalidated"
EVOLUTION_RUN_STAGE_REJECTED = "rejected"

EVOLUTION_STAGE_PLANNED = EVOLUTION_RUN_STAGE_PLANNED
EVOLUTION_STAGE_DATASET_BUILT = EVOLUTION_RUN_STAGE_DATASET_BUILT
EVOLUTION_STAGE_HARNESS_PLANNED = EVOLUTION_RUN_STAGE_HARNESS_PLANNED
EVOLUTION_STAGE_CONSTRAINTS_EVALUATED = EVOLUTION_RUN_STAGE_CONSTRAINTS_EVALUATED
EVOLUTION_STAGE_FITNESS_EVALUATED = EVOLUTION_RUN_STAGE_FITNESS_EVALUATED
EVOLUTION_STAGE_REPORT_BUILT = EVOLUTION_RUN_STAGE_REPORT_BUILT
EVOLUTION_STAGE_FAILED = EVOLUTION_RUN_STAGE_FAILED

EVOLUTION_READ_ONLY_STAGE_SEQUENCE = (
    EVOLUTION_RUN_STAGE_PLANNED,
    EVOLUTION_RUN_STAGE_DATASET_BUILT,
    EVOLUTION_RUN_STAGE_HARNESS_PLANNED,
    EVOLUTION_RUN_STAGE_CONSTRAINTS_EVALUATED,
    EVOLUTION_RUN_STAGE_FITNESS_EVALUATED,
    EVOLUTION_RUN_STAGE_REPORT_BUILT,
    EVOLUTION_RUN_STAGE_FAILED,
)

EVOLUTION_EXTENSION_STAGE_SEQUENCE = (
    EVOLUTION_RUN_STAGE_READY_FOR_REVIEW,
    EVOLUTION_RUN_STAGE_FOLLOWUP_REQUESTED,
    EVOLUTION_RUN_STAGE_PROMOTED,
    EVOLUTION_RUN_STAGE_INVALIDATED,
    EVOLUTION_RUN_STAGE_REJECTED,
)

EVOLUTION_READ_ONLY_RUN_STAGES = EVOLUTION_READ_ONLY_STAGE_SEQUENCE
EVOLUTION_FOLLOWUP_RUN_STAGES = EVOLUTION_EXTENSION_STAGE_SEQUENCE
EVOLUTION_ALL_RUN_STAGES = EVOLUTION_READ_ONLY_STAGE_SEQUENCE + EVOLUTION_EXTENSION_STAGE_SEQUENCE

EvolutionRunStage: TypeAlias = Literal[
    "planned",
    "dataset_built",
    "harness_planned",
    "constraints_evaluated",
    "fitness_evaluated",
    "report_built",
    "failed",
    "ready_for_review",
    "followup_requested",
    "promoted",
    "invalidated",
    "rejected",
]


@dataclass(frozen=True, slots=True)
class EvolutionStageContract:
    stage: EvolutionRunStage
    input_contract: str
    output_artifact: str
    invariants: tuple[str, ...]
    failure_shape: tuple[str, ...]
    future_only: bool = False


@dataclass(frozen=True, slots=True)
class EvolutionStageFailure:
    stage: EvolutionRunStage
    code: str
    message: str
    partial_results: tuple[str, ...] = ()
    recoverable: bool = False


EVOLUTION_FAILURE_SHAPE = (
    "stage",
    "code",
    "message",
    "partial_results",
    "recoverable",
)

EVOLUTION_STAGE_CONTRACTS = (
    EvolutionStageContract(
        stage=EVOLUTION_RUN_STAGE_PLANNED,
        input_contract="repository root and selected evolution targets",
        output_artifact="EvolutionRun plan",
        invariants=(
            "the repository root exists",
            "at least one target is selected",
            "live task state mutation remains disabled",
        ),
        failure_shape=EVOLUTION_FAILURE_SHAPE,
    ),
    EvolutionStageContract(
        stage=EVOLUTION_RUN_STAGE_DATASET_BUILT,
        input_contract="planned run plus repository-local task and event traces",
        output_artifact="EvolutionDataset",
        invariants=(
            "dataset repo_root matches the run repo_root",
            "selected task ids remain stable for the run",
            "dataset extraction does not mutate live task state",
        ),
        failure_shape=EVOLUTION_FAILURE_SHAPE,
    ),
    EvolutionStageContract(
        stage=EVOLUTION_RUN_STAGE_HARNESS_PLANNED,
        input_contract="planned run plus dataset",
        output_artifact="EvolutionHarnessPlan",
        invariants=(
            "baseline and candidate reference the same dataset scope",
            "harness planning remains evaluation-only",
            "the isolation mode is explicit",
        ),
        failure_shape=EVOLUTION_FAILURE_SHAPE,
    ),
    EvolutionStageContract(
        stage=EVOLUTION_RUN_STAGE_CONSTRAINTS_EVALUATED,
        input_contract="harness plan plus comparable metric placeholders",
        output_artifact="EvolutionConstraintResult",
        invariants=(
            "guard results remain tied to the current run id",
            "pending metrics are represented explicitly rather than inferred",
            "constraint results do not imply promotion or execution authority",
        ),
        failure_shape=EVOLUTION_FAILURE_SHAPE,
    ),
    EvolutionStageContract(
        stage=EVOLUTION_RUN_STAGE_FITNESS_EVALUATED,
        input_contract="harness plan plus constraints result",
        output_artifact="EvolutionFitnessResult",
        invariants=(
            "fitness is evaluated against the same harness scope",
            "guard failures keep candidate promotion ineligible",
            "missing metrics remain explicit pending values",
        ),
        failure_shape=EVOLUTION_FAILURE_SHAPE,
    ),
    EvolutionStageContract(
        stage=EVOLUTION_RUN_STAGE_REPORT_BUILT,
        input_contract="planned run plus dataset, harness, constraints, and fitness results",
        output_artifact="EvolutionReport",
        invariants=(
            "report scope matches the run and dataset repo_root",
            "the report remains review-oriented rather than execution-oriented",
            "report generation preserves the no-live-mutation boundary",
        ),
        failure_shape=EVOLUTION_FAILURE_SHAPE,
    ),
    EvolutionStageContract(
        stage=EVOLUTION_RUN_STAGE_FAILED,
        input_contract="stage-aware failure metadata plus any partial results already produced",
        output_artifact="EvolutionStageFailure",
        invariants=(
            "the stopping stage is recorded explicitly",
            "partial results remain attached to the failure",
            "failure reporting does not collapse into an opaque exception message",
        ),
        failure_shape=EVOLUTION_FAILURE_SHAPE,
    ),
    EvolutionStageContract(
        stage=EVOLUTION_RUN_STAGE_READY_FOR_REVIEW,
        input_contract="future follow-up review inputs",
        output_artifact="future follow-up review record",
        invariants=("future stage only; not a current runtime obligation",),
        failure_shape=EVOLUTION_FAILURE_SHAPE,
        future_only=True,
    ),
    EvolutionStageContract(
        stage=EVOLUTION_RUN_STAGE_FOLLOWUP_REQUESTED,
        input_contract="future handoff payload and operator-approved request context",
        output_artifact="future Sisyphus follow-up request",
        invariants=("future stage only; not a current runtime obligation",),
        failure_shape=EVOLUTION_FAILURE_SHAPE,
        future_only=True,
    ),
    EvolutionStageContract(
        stage=EVOLUTION_RUN_STAGE_PROMOTED,
        input_contract="future promotion evidence and receipts",
        output_artifact="future promotion decision",
        invariants=("future stage only; not a current runtime obligation",),
        failure_shape=EVOLUTION_FAILURE_SHAPE,
        future_only=True,
    ),
    EvolutionStageContract(
        stage=EVOLUTION_RUN_STAGE_INVALIDATED,
        input_contract="future invalidation evidence and dependency changes",
        output_artifact="future invalidation record",
        invariants=("future stage only; not a current runtime obligation",),
        failure_shape=EVOLUTION_FAILURE_SHAPE,
        future_only=True,
    ),
    EvolutionStageContract(
        stage=EVOLUTION_RUN_STAGE_REJECTED,
        input_contract="future review rejection context",
        output_artifact="future rejection record",
        invariants=("future stage only; not a current runtime obligation",),
        failure_shape=EVOLUTION_FAILURE_SHAPE,
        future_only=True,
    ),
)


def list_evolution_stage_contracts(*, include_future: bool = True) -> tuple[EvolutionStageContract, ...]:
    if include_future:
        return EVOLUTION_STAGE_CONTRACTS
    return tuple(contract for contract in EVOLUTION_STAGE_CONTRACTS if not contract.future_only)


def get_evolution_stage_contract(stage: EvolutionRunStage) -> EvolutionStageContract:
    for contract in EVOLUTION_STAGE_CONTRACTS:
        if contract.stage == stage:
            return contract
    raise ValueError(f"unknown evolution stage: {stage}")
