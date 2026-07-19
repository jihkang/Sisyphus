from __future__ import annotations

from typing import Protocol


class FeatureTaskArtifactSnapshotStatusLike(Protocol):
    status: str
    fingerprint: str | None
    current_fingerprint: str | None
    reason: str | None


def encode_feature_task_artifact_snapshot_status(
    value: FeatureTaskArtifactSnapshotStatusLike,
) -> dict[str, object]:
    data: dict[str, object] = {"status": value.status}
    if value.fingerprint is not None:
        data["fingerprint"] = value.fingerprint
    if value.current_fingerprint is not None:
        data["current_fingerprint"] = value.current_fingerprint
    if value.reason is not None:
        data["reason"] = value.reason
    return data


__all__ = ["encode_feature_task_artifact_snapshot_status"]
