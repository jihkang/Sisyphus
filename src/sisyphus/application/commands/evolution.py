from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class RequestEvolutionFollowupCommand:
    message: str
    title: str
    task_type: str
    slug: str
    instruction: str | None
    owned_paths: tuple[str, ...] = ()
    source_context: dict[str, object] = field(default_factory=dict)


__all__ = ["RequestEvolutionFollowupCommand"]
