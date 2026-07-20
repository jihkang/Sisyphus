from __future__ import annotations

import re


EVOLUTION_RUN_ARTIFACT_NAMES = frozenset(
    {
        "run.json",
        "dataset.json",
        "harness_plan.json",
        "constraints.json",
        "fitness.json",
        "report.md",
        "failure.json",
    }
)
_EVOLUTION_RUN_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,199}$")


def validate_evolution_run_id(run_id: str) -> str:
    normalized = str(run_id).strip()
    if not _EVOLUTION_RUN_ID_PATTERN.fullmatch(normalized):
        raise ValueError(f"invalid evolution run id: {run_id!r}")
    return normalized


def validate_evolution_artifact_name(name: str) -> str:
    normalized = str(name).strip()
    if normalized not in EVOLUTION_RUN_ARTIFACT_NAMES:
        raise ValueError(f"unsupported evolution run artifact: {name!r}")
    return normalized


__all__ = [
    "EVOLUTION_RUN_ARTIFACT_NAMES",
    "validate_evolution_artifact_name",
    "validate_evolution_run_id",
]
