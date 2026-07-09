from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


Gate = dict[str, Any]


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def make_gate(
    code: str,
    message: str,
    source: str,
    *,
    blocking: bool = True,
    severity: str | None = None,
    checkpoint_type: str | None = None,
    subtask_id: str | None = None,
    created_at: str | None = None,
) -> Gate:
    gate: Gate = {
        "code": code,
        "message": message,
        "blocking": blocking,
        "source": source,
        "created_at": created_at or utc_now(),
    }
    if severity:
        gate["severity"] = severity
    if checkpoint_type:
        gate["checkpoint_type"] = checkpoint_type
    if subtask_id:
        gate["subtask_id"] = subtask_id
    return gate


def dedupe_gates(gates: list[dict]) -> list[dict]:
    seen: set[tuple[object, object, object, object]] = set()
    deduped: list[dict] = []
    for gate in gates:
        key = (
            gate.get("code", ""),
            gate.get("message", ""),
            gate.get("checkpoint_type"),
            gate.get("subtask_id"),
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(gate)
    return deduped


def blocking_gates(gates: list[dict]) -> list[dict]:
    return [gate for gate in gates if bool(gate.get("blocking", True))]


__all__ = ["Gate", "blocking_gates", "dedupe_gates", "make_gate"]
