from __future__ import annotations

from ..action_space import ActionSpec


def encode_action_spec(spec: ActionSpec) -> dict[str, object]:
    return {
        "name": spec.name,
        "risk": spec.risk.value,
        "allowed_for_policy": spec.allowed_for_policy,
        "requires_human": spec.requires_human,
        "mutates_state": spec.mutates_state,
        "description": spec.description,
        "lifecycle_action": (
            spec.lifecycle_action.value if spec.lifecycle_action is not None else None
        ),
    }


__all__ = ["encode_action_spec"]
