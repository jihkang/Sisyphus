from __future__ import annotations

from .domain.promotion import service as _service
from .domain.promotion.service import *  # noqa: F403

_run_gh = _service._run_gh


def execute_promotion(*args, **kwargs):
    _service._run_gh = _run_gh
    return _service.execute_promotion(*args, **kwargs)


def record_merged_pull_request(*args, **kwargs):
    _service._run_gh = _run_gh
    return _service.record_merged_pull_request(*args, **kwargs)


def __getattr__(name: str) -> object:
    return getattr(_service, name)
