from __future__ import annotations

import importlib
import sys

from taskflow.evolution import *  # noqa: F403

_ALIASED_SUBMODULES = (
    "constraints",
    "dataset",
    "fitness",
    "harness",
    "report",
    "runner",
    "targets",
)


def _install_submodule_aliases() -> None:
    for submodule_name in _ALIASED_SUBMODULES:
        module = importlib.import_module(f"taskflow.evolution.{submodule_name}")
        alias = f"{__name__}.{submodule_name}"
        sys.modules.setdefault(alias, module)
        globals().setdefault(submodule_name, module)


_install_submodule_aliases()
