from __future__ import annotations

from pathlib import Path

from .config import SisyphusConfig
from .infra.orchestration import workflow as _service
from .infra.orchestration.workflow import *  # noqa: F403

run_provider_wrapper = _service.run_provider_wrapper


def run_workflow_cycle(repo_root: Path, config: SisyphusConfig) -> int:
    _service.run_provider_wrapper = run_provider_wrapper
    return _service.run_workflow_cycle(repo_root=repo_root, config=config)


def __getattr__(name: str) -> object:
    return getattr(_service, name)
