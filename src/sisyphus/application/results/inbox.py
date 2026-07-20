from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class DaemonStats:
    processed: int = 0
    failed: int = 0
    skipped: int = 0
    orchestrated: int = 0


__all__ = ["DaemonStats"]
