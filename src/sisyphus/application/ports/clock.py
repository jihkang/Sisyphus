from __future__ import annotations

from typing import Protocol


class ClockPort(Protocol):
    def now(self) -> str: ...


__all__ = ["ClockPort"]
