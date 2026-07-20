from __future__ import annotations

from collections.abc import Mapping
import hashlib
import json
import math
from pathlib import PurePosixPath

from .verification_evidence import DEFAULT_EVIDENCE_GRAPH_PATH


REVIEW_BINDING_FIELDS = (
    "envelope_digest",
    "report_digest",
    "reviewed_head_sha",
    "scope_digest",
)


def external_review_scope_document_paths(task: Mapping[str, object]) -> tuple[str, ...]:
    task_dir = _normalized_relative_path(task.get("task_dir"), field="task_dir")
    paths: set[str] = set()
    docs = task.get("docs")
    if isinstance(docs, Mapping):
        keys = ("brief", "plan") if task.get("type") == "feature" else ("brief", "repro", "fix_plan")
        for key in keys:
            _add_task_document_path(paths, task_dir, docs.get(key), field=f"docs.{key}")

    design = task.get("design")
    if isinstance(design, Mapping):
        frozen = design.get("frozen")
        if isinstance(frozen, Mapping):
            artifacts = frozen.get("artifacts")
            if isinstance(artifacts, Mapping):
                for key, value in artifacts.items():
                    _add_task_document_path(
                        paths,
                        task_dir,
                        value,
                        field=f"design.frozen.artifacts.{key}",
                    )

    validation = task.get("spec_validation")
    if isinstance(validation, Mapping):
        _add_task_document_path(
            paths,
            task_dir,
            validation.get("report_path"),
            field="spec_validation.report_path",
        )
    return tuple(sorted(paths))


def build_external_review_scope_payload(
    task: Mapping[str, object],
    document_digests: Mapping[str, str | None],
) -> dict[str, object]:
    strategy = task.get("test_strategy")
    strategy_mapping = strategy if isinstance(strategy, Mapping) else {}
    review = strategy_mapping.get("external_llm")
    review_mapping = review if isinstance(review, Mapping) else {}
    design = task.get("design")
    design_mapping = design if isinstance(design, Mapping) else {}
    validation = task.get("spec_validation")
    validation_mapping = validation if isinstance(validation, Mapping) else {}
    promotion = task.get("promotion")
    promotion_mapping = promotion if isinstance(promotion, Mapping) else {}
    meta = task.get("meta")
    meta_mapping = meta if isinstance(meta, Mapping) else {}

    return {
        "schema_version": "sisyphus.external_review_scope.v1",
        "task": _select(
            task,
            (
                "id",
                "type",
                "slug",
                "branch",
                "base_branch",
                "plan_status",
                "spec_status",
                "spec_frozen_at",
                "verify_profile",
                "verify_commands",
            ),
        ),
        "test_strategy": {
            **_select(
                strategy_mapping,
                ("normal_cases", "edge_cases", "exception_cases", "verification_methods"),
            ),
            "external_llm": _select(
                review_mapping,
                ("required", "provider", "purpose", "trigger"),
            ),
        },
        "design_frozen": _json_value(design_mapping.get("frozen")),
        "spec_validation": _select(
            validation_mapping,
            ("status", "stale", "report_path", "source_fingerprint", "error_count", "warning_count"),
        ),
        "promotion_policy": _select(
            promotion_mapping,
            ("required", "strategy", "base_branch", "parent_task_id", "parent_artifact_id"),
        ),
        "owned_paths": _json_value(meta_mapping.get("owned_paths", [])),
        "documents": {
            str(path): document_digests[path]
            for path in sorted(document_digests)
        },
    }


def external_review_scope_digest(
    task: Mapping[str, object],
    document_digests: Mapping[str, str | None],
) -> str:
    payload = build_external_review_scope_payload(task, document_digests)
    canonical = json.dumps(
        payload,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return f"sha256:{hashlib.sha256(canonical).hexdigest()}"


def external_review_artifact_prefix(task: Mapping[str, object]) -> str:
    task_dir = _normalized_relative_path(task.get("task_dir"), field="task_dir")
    return (PurePosixPath(task_dir) / "artifacts" / "reviews").as_posix()


def external_review_post_verification_paths(
    task: Mapping[str, object],
) -> tuple[str, ...]:
    task_dir = _normalized_relative_path(task.get("task_dir"), field="task_dir")
    paths = {
        (PurePosixPath(task_dir) / DEFAULT_EVIDENCE_GRAPH_PATH).as_posix(),
    }
    docs = task.get("docs")
    if isinstance(docs, Mapping) and docs.get("verify") not in (None, ""):
        _add_task_document_path(
            paths,
            task_dir,
            docs.get("verify"),
            field="docs.verify",
        )
    return tuple(sorted(paths))


def external_review_binding(review: Mapping[str, object], *, verified_at: str) -> dict[str, str]:
    binding = {
        field: str(review.get(field) or "").strip().lower()
        for field in REVIEW_BINDING_FIELDS
    }
    if not all(binding.values()):
        raise ValueError("external review is missing verification-binding metadata")
    binding["verified_at"] = verified_at
    return binding


def external_review_binding_is_current(task: Mapping[str, object]) -> bool:
    strategy = task.get("test_strategy")
    if not isinstance(strategy, Mapping):
        return True
    review = strategy.get("external_llm")
    if not isinstance(review, Mapping) or not review.get("required"):
        return True
    if review.get("status") != "passed":
        return False
    binding = review.get("verification_binding")
    if not isinstance(binding, Mapping):
        return False
    return all(
        str(binding.get(field) or "").strip().lower()
        == str(review.get(field) or "").strip().lower()
        and bool(str(review.get(field) or "").strip())
        for field in REVIEW_BINDING_FIELDS
    )


def _add_task_document_path(
    paths: set[str],
    task_dir: str,
    value: object,
    *,
    field: str,
) -> None:
    if value in (None, ""):
        return
    relative = _normalized_relative_path(value, field=field)
    paths.add((PurePosixPath(task_dir) / relative).as_posix())


def _normalized_relative_path(value: object, *, field: str) -> str:
    raw = str(value or "").strip()
    if not raw or "\\" in raw or "\x00" in raw:
        raise ValueError(f"{field} must be a normalized relative POSIX path")
    path = PurePosixPath(raw)
    if (
        path.is_absolute()
        or path == PurePosixPath(".")
        or ".." in path.parts
        or raw != path.as_posix()
        or any(part in {"", "."} for part in path.parts)
    ):
        raise ValueError(f"{field} must be a normalized relative POSIX path")
    return path.as_posix()


def _select(source: Mapping[str, object], fields: tuple[str, ...]) -> dict[str, object]:
    return {field: _json_value(source.get(field)) for field in fields}


def _json_value(value: object) -> object:
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError("external review scope contains a non-finite number")
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, Mapping):
        return {
            str(key): _json_value(item)
            for key, item in sorted(value.items(), key=lambda entry: str(entry[0]))
        }
    if isinstance(value, (list, tuple)):
        return [_json_value(item) for item in value]
    raise TypeError(f"external review scope contains unsupported value: {type(value).__name__}")


__all__ = [
    "REVIEW_BINDING_FIELDS",
    "build_external_review_scope_payload",
    "external_review_artifact_prefix",
    "external_review_binding",
    "external_review_binding_is_current",
    "external_review_post_verification_paths",
    "external_review_scope_digest",
    "external_review_scope_document_paths",
]
