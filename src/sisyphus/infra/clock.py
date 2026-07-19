from __future__ import annotations

from ..shared.clock import utc_now


class SystemClock:
    def now(self) -> str:
        return utc_now()


__all__ = ["SystemClock"]
