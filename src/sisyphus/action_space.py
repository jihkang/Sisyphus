from __future__ import annotations

from .application.action_space import ACTION_REGISTRY, ActionRiskLevel, ActionSpec
from .application.codecs.action_space import encode_action_spec
from .compat.serialization import install_serialization_compat
from .composition.action_space import allowed_policy_actions, forbidden_policy_actions


install_serialization_compat(ActionSpec, encode_mapping=encode_action_spec)


__all__ = [
    "ACTION_REGISTRY",
    "ActionRiskLevel",
    "ActionSpec",
    "allowed_policy_actions",
    "forbidden_policy_actions",
]
