from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class GateSpec:
    code: str
    message: str
    source: str
    blocking: bool = True
    severity: str | None = None
    checkpoint_type: str | None = None
    subtask_id: str | None = None

    @property
    def identity(self) -> tuple[str, str, str | None, str | None]:
        return (self.code, self.message, self.checkpoint_type, self.subtask_id)


def dedupe_gate_specs(gates: tuple[GateSpec, ...] | list[GateSpec]) -> tuple[GateSpec, ...]:
    seen: set[tuple[str, str, str | None, str | None]] = set()
    result: list[GateSpec] = []
    for gate in gates:
        if gate.identity in seen:
            continue
        seen.add(gate.identity)
        result.append(gate)
    return tuple(result)


__all__ = ["GateSpec", "dedupe_gate_specs"]
