from __future__ import annotations

from ..application.results.agent import AgentView
from ..shared.serialization import to_json_value


def present_agent(view: AgentView) -> dict[str, object]:
    payload = to_json_value(view.agent)
    if not isinstance(payload, dict):
        raise TypeError("agent view must serialize to an object")
    payload["raw_status"] = view.raw_status
    payload["status"] = view.effective_status
    return payload


__all__ = ["present_agent"]
