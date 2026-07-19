from __future__ import annotations


def extract_conformance_summary(entity: dict) -> dict[str, object] | None:
    conformance = entity.get("conformance")
    if not isinstance(conformance, dict):
        meta = entity.get("meta")
        if isinstance(meta, dict):
            conformance = meta.get("conformance")
    if not isinstance(conformance, dict):
        return None

    summary: dict[str, object] = {}
    aliases: dict[str, tuple[str, ...]] = {
        "status": ("status", "color"),
        "last_spec_anchor_at": (
            "last_spec_anchor_at",
            "spec_anchor_at",
            "anchored_at",
        ),
        "last_checkpoint_type": (
            "last_checkpoint_type",
            "checkpoint_type",
            "checkpoint",
        ),
        "drift_count": ("drift_count", "drifts", "drift"),
        "summary": ("summary", "last_summary", "message"),
    }
    for target_key, candidate_keys in aliases.items():
        for candidate_key in candidate_keys:
            value = conformance.get(candidate_key)
            if value not in (None, ""):
                summary[target_key] = value
                break
    return summary or None


def format_conformance_summary(summary: dict[str, object] | None) -> str | None:
    if not summary:
        return None
    parts: list[str] = []
    status = summary.get("status")
    if status not in (None, ""):
        parts.append(str(status))
    anchor = summary.get("last_spec_anchor_at")
    if anchor not in (None, ""):
        parts.append(f"anchor={anchor}")
    checkpoint = summary.get("last_checkpoint_type")
    if checkpoint not in (None, ""):
        parts.append(f"checkpoint={checkpoint}")
    drift_count = summary.get("drift_count")
    if drift_count not in (None, ""):
        parts.append(f"drift={drift_count}")
    note = summary.get("summary")
    if note not in (None, ""):
        parts.append(f"note={note}")
    return " ".join(parts)


def summarize_subtask_conformance(task: dict) -> str | None:
    subtasks = task.get("subtasks")
    if not isinstance(subtasks, list):
        return None
    counts: dict[str, int] = {}
    for subtask in subtasks:
        if not isinstance(subtask, dict):
            continue
        summary = extract_conformance_summary(subtask)
        if summary is None:
            continue
        status = str(summary.get("status") or "unknown").lower()
        counts[status] = counts.get(status, 0) + 1
    if not counts:
        return None
    order = ("green", "yellow", "red", "unknown")
    parts = [f"{status}:{counts[status]}" for status in order if counts.get(status)]
    parts.extend(
        f"{status}:{count}"
        for status, count in sorted(counts.items())
        if status not in order
    )
    return " ".join(parts)


__all__ = [
    "extract_conformance_summary",
    "format_conformance_summary",
    "summarize_subtask_conformance",
]
