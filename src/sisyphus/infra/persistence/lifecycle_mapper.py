from __future__ import annotations

from ...application.lifecycle_records import lifecycle_snapshot_from_record
from ...application.planning_records import gate_spec_to_record
from ...domain.lifecycle import GateSpec, LifecycleAction, LifecycleSnapshot
from ...shared.clock import utc_now


class LifecycleRecordMapper:
    """Compatibility mapper for the canonical application record projection."""

    @staticmethod
    def to_domain(task: dict, *, action: LifecycleAction) -> LifecycleSnapshot:
        return lifecycle_snapshot_from_record(task, action=action)

    @staticmethod
    def gate_to_record(gate: GateSpec) -> dict:
        return gate_spec_to_record(gate, created_at=utc_now())


__all__ = ["LifecycleRecordMapper"]
