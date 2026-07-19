from __future__ import annotations

from pathlib import Path

from ..infra.validation.spec_validation import spec_validation_resource_payload


def build_spec_validation_resource(
    task: dict[str, object],
    task_dir: Path,
) -> dict[str, object]:
    return spec_validation_resource_payload(task, task_dir)


__all__ = ["build_spec_validation_resource"]
