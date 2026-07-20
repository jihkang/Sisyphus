from __future__ import annotations

from importlib import import_module
from pathlib import Path


def run_legacy_provider_wrapper(
    provider: str,
    argv: list[str],
    *,
    repo_root: Path | None = None,
) -> int:
    wrapper = import_module("sisyphus.provider_wrapper")
    return wrapper.run_provider_wrapper(provider, argv, repo_root=repo_root)


__all__ = ["run_legacy_provider_wrapper"]
