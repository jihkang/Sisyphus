from __future__ import annotations

from collections.abc import Mapping
import hashlib
import json
import math
from pathlib import PurePosixPath

from .promotion_projection import DEFAULT_PROMOTION_EXECUTION_RECEIPT_PATH
from .verification_evidence import DEFAULT_EVIDENCE_GRAPH_PATH


REVIEW_BINDING_FIELDS = (
    "envelope_digest",
    "report_digest",
    "reviewed_head_sha",
    "scope_digest",
)
VERIFICATION_OUTPUT_PATHS_FIELD = "verification_output_paths"
PROMOTION_OUTPUT_PATHS_FIELD = "promotion_output_paths"


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
                "task_dir",
                "worktree_path",
            ),
        ),
        "task_docs": _json_value(task.get("docs", {})),
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
        "promotion_policy": {
            **_select(
                promotion_mapping,
                ("required", "strategy", "base_branch", "parent_task_id", "parent_artifact_id"),
            ),
            "execution_receipt_path": (
                _normalized_relative_path(
                    promotion_mapping.get("execution_receipt_path")
                    or DEFAULT_PROMOTION_EXECUTION_RECEIPT_PATH,
                    field="promotion.execution_receipt_path",
                )
                if promotion_mapping.get("required")
                else None
            ),
        },
        "generated_outputs": {
            "verification": list(external_review_verification_output_paths(task)),
            "promotion": list(external_review_promotion_output_paths(task)),
        },
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


def external_review_verification_output_paths(
    task: Mapping[str, object],
) -> tuple[str, ...]:
    paths = {DEFAULT_EVIDENCE_GRAPH_PATH}
    docs = task.get("docs")
    if not isinstance(docs, Mapping) or docs.get("verify") in (None, ""):
        raise ValueError("docs.verify must identify the verification document")
    verify_path = _normalized_relative_path(docs.get("verify"), field="docs.verify")
    if verify_path == DEFAULT_EVIDENCE_GRAPH_PATH:
        raise ValueError("docs.verify must not collide with the evidence graph")
    paths.add(verify_path)
    return tuple(sorted(paths))


def external_review_promotion_output_paths(
    task: Mapping[str, object],
) -> tuple[str, ...]:
    promotion = task.get("promotion")
    if not isinstance(promotion, Mapping) or not promotion.get("required"):
        return ()
    receipt_path = _normalized_relative_path(
        promotion.get("execution_receipt_path")
        or DEFAULT_PROMOTION_EXECUTION_RECEIPT_PATH,
        field="promotion.execution_receipt_path",
    )
    if receipt_path in external_review_verification_output_paths(task):
        raise ValueError("promotion receipt must not collide with verification outputs")
    return (receipt_path,)


def external_review_recorded_output_paths(
    review: Mapping[str, object],
    *,
    field: str,
) -> tuple[str, ...]:
    raw = review.get(field)
    if not isinstance(raw, (list, tuple)) or not raw:
        raise ValueError(f"external review is missing {field}")
    paths = tuple(
        sorted(
            {
                _normalized_relative_path(value, field=f"external_review.{field}")
                for value in raw
            }
        )
    )
    if len(paths) != len(raw):
        raise ValueError(f"external review {field} contains duplicate paths")
    return paths


def validate_external_review_output_paths(
    task: Mapping[str, object],
    review: Mapping[str, object],
) -> None:
    expected_verification = external_review_verification_output_paths(task)
    recorded_verification = external_review_recorded_output_paths(
        review,
        field=VERIFICATION_OUTPUT_PATHS_FIELD,
    )
    if recorded_verification != expected_verification:
        raise ValueError("external review verification output paths no longer match the task")

    expected_promotion = external_review_promotion_output_paths(task)
    raw_promotion = review.get(PROMOTION_OUTPUT_PATHS_FIELD)
    if expected_promotion:
        recorded_promotion = external_review_recorded_output_paths(
            review,
            field=PROMOTION_OUTPUT_PATHS_FIELD,
        )
    elif raw_promotion in (None, [], ()):
        recorded_promotion = ()
    else:
        recorded_promotion = external_review_recorded_output_paths(
            review,
            field=PROMOTION_OUTPUT_PATHS_FIELD,
        )
    if recorded_promotion != expected_promotion:
        raise ValueError("external review promotion output paths no longer match the task")


def external_review_post_verification_paths(
    task: Mapping[str, object],
    review: Mapping[str, object] | None = None,
) -> tuple[str, ...]:
    task_dir = _normalized_relative_path(task.get("task_dir"), field="task_dir")
    relative_paths = (
        external_review_recorded_output_paths(
            review,
            field=VERIFICATION_OUTPUT_PATHS_FIELD,
        )
        if review is not None
        else external_review_verification_output_paths(task)
    )
    return tuple(
        sorted((PurePosixPath(task_dir) / path).as_posix() for path in relative_paths)
    )


def external_review_post_promotion_paths(
    task: Mapping[str, object],
    review: Mapping[str, object] | None = None,
) -> tuple[str, ...]:
    task_dir = _normalized_relative_path(task.get("task_dir"), field="task_dir")
    if review is not None:
        raw = review.get(PROMOTION_OUTPUT_PATHS_FIELD)
        relative_paths = (
            ()
            if raw in (None, [], ())
            else external_review_recorded_output_paths(
                review,
                field=PROMOTION_OUTPUT_PATHS_FIELD,
            )
        )
    else:
        relative_paths = external_review_promotion_output_paths(task)
    return tuple(
        sorted((PurePosixPath(task_dir) / path).as_posix() for path in relative_paths)
    )


def external_review_verify_document_path(
    task: Mapping[str, object],
    review: Mapping[str, object] | None,
) -> str:
    if review is None:
        docs = task.get("docs")
        if not isinstance(docs, Mapping):
            raise ValueError("task docs must be a mapping")
        return _normalized_relative_path(docs.get("verify"), field="docs.verify")
    paths = external_review_recorded_output_paths(
        review,
        field=VERIFICATION_OUTPUT_PATHS_FIELD,
    )
    documents = tuple(path for path in paths if path != DEFAULT_EVIDENCE_GRAPH_PATH)
    if len(documents) != 1:
        raise ValueError("external review must bind exactly one verification document")
    return documents[0]


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
    "PROMOTION_OUTPUT_PATHS_FIELD",
    "REVIEW_BINDING_FIELDS",
    "VERIFICATION_OUTPUT_PATHS_FIELD",
    "build_external_review_scope_payload",
    "external_review_artifact_prefix",
    "external_review_binding",
    "external_review_binding_is_current",
    "external_review_post_promotion_paths",
    "external_review_post_verification_paths",
    "external_review_promotion_output_paths",
    "external_review_recorded_output_paths",
    "external_review_scope_digest",
    "external_review_scope_document_paths",
    "external_review_verification_output_paths",
    "external_review_verify_document_path",
    "validate_external_review_output_paths",
]
