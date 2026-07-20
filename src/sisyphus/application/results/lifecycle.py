from __future__ import annotations

from dataclasses import dataclass

from ...domain.lifecycle.models import LifecycleAction, WorkflowPhase


@dataclass(frozen=True, slots=True)
class TransitionResult:
    allowed: bool
    action: LifecycleAction
    current_phase: str | None
    next_phase: str | None
    gates: tuple[dict, ...]
    reason: str

    @property
    def blocking_codes(self) -> tuple[str, ...]:
        return tuple(str(gate.get("code")) for gate in self.gates if gate.get("blocking", True))


__all__ = ["LifecycleAction", "TransitionResult", "WorkflowPhase"]
