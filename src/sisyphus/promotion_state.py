from __future__ import annotations

import copy


PROMOTION_STATUS_NOT_REQUIRED = "not_required"
PROMOTION_STATUS_PENDING = "promotion_pending"
PROMOTION_STATUS_COMMITTED = "committed"
PROMOTION_STATUS_PUSHED = "pushed"
PROMOTION_STATUS_PR_OPEN = "pr_open"
PROMOTION_STATUS_MERGED = "merged"
PROMOTION_STATUS_RECORDED = "promotion_recorded"
PROMOTION_STATUSES = {
    PROMOTION_STATUS_NOT_REQUIRED,
    PROMOTION_STATUS_PENDING,
    PROMOTION_STATUS_COMMITTED,
    PROMOTION_STATUS_PUSHED,
    PROMOTION_STATUS_PR_OPEN,
    PROMOTION_STATUS_MERGED,
    PROMOTION_STATUS_RECORDED,
}

PROMOTION_STRATEGY_DIRECT = "direct"
PROMOTION_STRATEGY_STACKED = "stacked"
PROMOTION_STRATEGIES = {
    PROMOTION_STRATEGY_DIRECT,
    PROMOTION_STRATEGY_STACKED,
}
NON_PROMOTABLE_PATH_PREFIXES = (
    ".planning/",
    "tests/",
    "test/",
)


def default_task_promotion() -> dict:
    return {
        "required": False,
        "required_override": None,
        "required_reason": None,
        "required_source": None,
        "status": PROMOTION_STATUS_NOT_REQUIRED,
        "strategy": PROMOTION_STRATEGY_DIRECT,
        "remote_name": None,
        "parent_artifact_id": None,
        "parent_task_id": None,
        "base_override": None,
        "base_branch": None,
        "base_source": None,
        "base_reason": None,
        "resolved_parent_branch": None,
        "retarget_required": False,
        "reverify_required": False,
        "retarget_required_at": None,
        "retarget_parent_task_id": None,
        "retarget_parent_branch": None,
        "retarget_merge_target": None,
        "head_branch": None,
        "pr_number": None,
        "pr_url": None,
        "receipt_path": None,
        "execution_receipt_path": None,
        "changeset_path": None,
        "commit_message": None,
        "repo_full_name": None,
        "title": None,
        "head_sha": None,
        "merge_commit_sha": None,
        "committed_at": None,
        "pushed_at": None,
        "pr_opened_at": None,
        "merged_at": None,
        "merged_by": None,
        "merge_method": None,
        "recorded_at": None,
    }


def ensure_task_promotion_defaults(task: dict) -> dict:
    defaults = default_task_promotion()
    explicit_promotion = task.get("promotion") if isinstance(task.get("promotion"), dict) else None
    had_explicit_status = explicit_promotion is not None and explicit_promotion.get("status") not in (None, "")
    if not isinstance(task.get("promotion"), dict):
        task["promotion"] = copy.deepcopy(defaults)

    promotion = task["promotion"]
    for key, value in defaults.items():
        if key not in promotion:
            promotion[key] = copy.deepcopy(value)

    docs = dict(task.get("docs", {})) if isinstance(task.get("docs"), dict) else {}
    legacy = _legacy_promotion(task)

    promotion["required"] = _coerce_bool(promotion.get("required"))
    promotion["required_override"] = _coerce_optional_bool(promotion.get("required_override"))
    promotion["required_reason"] = _normalize_text_value(promotion.get("required_reason"))
    promotion["required_source"] = _normalize_text_value(promotion.get("required_source"))
    promotion["strategy"] = normalize_promotion_strategy(promotion.get("strategy"))
    promotion["remote_name"] = _normalize_text_value(promotion.get("remote_name"))

    promotion["parent_artifact_id"] = _coalesce_text(
        promotion.get("parent_artifact_id"),
        legacy.get("parent_artifact_id"),
    )
    promotion["parent_task_id"] = _coalesce_text(
        promotion.get("parent_task_id"),
        legacy.get("parent_task_id"),
        task.get("meta", {}).get("followup_of_task_id") if isinstance(task.get("meta"), dict) else None,
    )
    promotion["base_override"] = _normalize_text_value(promotion.get("base_override"))
    promotion["base_branch"] = _coalesce_text(
        promotion.get("base_branch"),
        legacy.get("base_branch"),
        task.get("base_branch"),
    )
    promotion["base_source"] = _normalize_text_value(promotion.get("base_source"))
    promotion["base_reason"] = _normalize_text_value(promotion.get("base_reason"))
    promotion["resolved_parent_branch"] = _normalize_text_value(promotion.get("resolved_parent_branch"))
    promotion["retarget_required"] = _coerce_bool(promotion.get("retarget_required"))
    promotion["reverify_required"] = _coerce_bool(promotion.get("reverify_required"))
    promotion["retarget_required_at"] = _normalize_text_value(promotion.get("retarget_required_at"))
    promotion["retarget_parent_task_id"] = _normalize_text_value(promotion.get("retarget_parent_task_id"))
    promotion["retarget_parent_branch"] = _normalize_text_value(promotion.get("retarget_parent_branch"))
    promotion["retarget_merge_target"] = _normalize_text_value(promotion.get("retarget_merge_target"))
    promotion["head_branch"] = _coalesce_text(
        promotion.get("head_branch"),
        legacy.get("head_branch"),
        task.get("branch"),
    )
    promotion["pr_number"] = _coalesce_int(
        promotion.get("pr_number"),
        legacy.get("pr_number"),
    )
    promotion["pr_url"] = _coalesce_text(
        promotion.get("pr_url"),
        legacy.get("url"),
    )
    promotion["receipt_path"] = _coalesce_text(
        promotion.get("receipt_path"),
        legacy.get("receipt_path"),
        docs.get("promotion"),
    )
    promotion["execution_receipt_path"] = _normalize_text_value(promotion.get("execution_receipt_path"))
    promotion["changeset_path"] = _coalesce_text(
        promotion.get("changeset_path"),
        legacy.get("changeset_path"),
        docs.get("changeset"),
    )
    promotion["commit_message"] = _normalize_text_value(promotion.get("commit_message"))
    promotion["repo_full_name"] = _coalesce_text(
        promotion.get("repo_full_name"),
        legacy.get("repo_full_name"),
    )
    promotion["title"] = _coalesce_text(
        promotion.get("title"),
        legacy.get("title"),
    )
    promotion["head_sha"] = _coalesce_text(
        promotion.get("head_sha"),
        legacy.get("head_sha"),
    )
    promotion["merge_commit_sha"] = _coalesce_text(
        promotion.get("merge_commit_sha"),
        legacy.get("merge_commit_sha"),
    )
    promotion["committed_at"] = _normalize_text_value(promotion.get("committed_at"))
    promotion["pushed_at"] = _normalize_text_value(promotion.get("pushed_at"))
    promotion["pr_opened_at"] = _normalize_text_value(promotion.get("pr_opened_at"))
    promotion["merged_at"] = _coalesce_text(
        promotion.get("merged_at"),
        legacy.get("merged_at"),
    )
    promotion["merged_by"] = _coalesce_text(
        promotion.get("merged_by"),
        legacy.get("merged_by"),
    )
    promotion["merge_method"] = _coalesce_text(
        promotion.get("merge_method"),
        legacy.get("merge_method"),
    )
    promotion["recorded_at"] = _coalesce_text(
        promotion.get("recorded_at"),
        legacy.get("recorded_at"),
    )

    if promotion["required_override"] is not None:
        promotion["required"] = promotion["required_override"]
        promotion["required_reason"] = "promotion requirement was overridden explicitly"
        promotion["required_source"] = "override"
    elif _promotion_has_material_state(promotion):
        promotion["required"] = True
        if promotion["required_reason"] is None:
            promotion["required_reason"] = "promotion metadata already exists for this task"
        promotion["required_source"] = "recorded"
    elif _should_auto_classify_task(task):
        promotion["required"], promotion["required_reason"] = classify_task_promotion_requirement(task)
        promotion["required_source"] = "classified"

    legacy_status = normalize_promotion_status(
        legacy.get("status"),
        required=promotion["required"],
        fallback=PROMOTION_STATUS_PENDING if promotion["required"] else PROMOTION_STATUS_NOT_REQUIRED,
    )
    if legacy_status == PROMOTION_STATUS_MERGED and legacy.get("receipt_path"):
        legacy_status = PROMOTION_STATUS_RECORDED

    raw_status = promotion.get("status")
    if not had_explicit_status and legacy_status in PROMOTION_STATUSES:
        raw_status = legacy_status

    promotion["status"] = normalize_promotion_status(
        raw_status,
        required=promotion["required"],
        fallback=legacy_status,
    )
    if promotion["required"] and promotion["status"] == PROMOTION_STATUS_NOT_REQUIRED:
        promotion["status"] = PROMOTION_STATUS_PENDING
    if not promotion["required"]:
        promotion["status"] = PROMOTION_STATUS_NOT_REQUIRED

    if not isinstance(task.get("meta"), dict):
        task["meta"] = {}
    meta = task["meta"]
    meta["promotion"] = legacy_promotion_projection(task)
    return task


def normalize_promotion_status(
    value: object | None,
    *,
    required: bool,
    fallback: str | None = None,
) -> str:
    normalized = _normalize_text_value(value)
    aliases = {
        "pending": PROMOTION_STATUS_PENDING,
        "ready": PROMOTION_STATUS_PENDING,
        "recorded": PROMOTION_STATUS_RECORDED,
    }
    if normalized is not None:
        normalized = aliases.get(normalized.lower(), normalized.lower())
    if normalized in PROMOTION_STATUSES:
        return str(normalized)
    if fallback in PROMOTION_STATUSES:
        return str(fallback)
    return PROMOTION_STATUS_PENDING if required else PROMOTION_STATUS_NOT_REQUIRED


def normalize_promotion_strategy(value: object | None) -> str:
    normalized = _normalize_text_value(value)
    if normalized is None:
        return PROMOTION_STRATEGY_DIRECT
    normalized = normalized.lower()
    if normalized not in PROMOTION_STRATEGIES:
        return PROMOTION_STRATEGY_DIRECT
    return normalized


def promotion_summary(task: dict) -> dict[str, object]:
    ensure_task_promotion_defaults(task)
    promotion = task["promotion"]
    return {
        "required": promotion.get("required", False),
        "required_override": promotion.get("required_override"),
        "required_reason": promotion.get("required_reason"),
        "required_source": promotion.get("required_source"),
        "status": promotion.get("status"),
        "strategy": promotion.get("strategy"),
        "remote_name": promotion.get("remote_name"),
        "parent_artifact_id": promotion.get("parent_artifact_id"),
        "parent_task_id": promotion.get("parent_task_id"),
        "base_override": promotion.get("base_override"),
        "base_branch": promotion.get("base_branch"),
        "base_source": promotion.get("base_source"),
        "base_reason": promotion.get("base_reason"),
        "resolved_parent_branch": promotion.get("resolved_parent_branch"),
        "retarget_required": promotion.get("retarget_required"),
        "reverify_required": promotion.get("reverify_required"),
        "retarget_required_at": promotion.get("retarget_required_at"),
        "retarget_parent_task_id": promotion.get("retarget_parent_task_id"),
        "retarget_parent_branch": promotion.get("retarget_parent_branch"),
        "retarget_merge_target": promotion.get("retarget_merge_target"),
        "head_branch": promotion.get("head_branch"),
        "pr_number": promotion.get("pr_number"),
        "pr_url": promotion.get("pr_url"),
        "receipt_path": promotion.get("receipt_path"),
        "execution_receipt_path": promotion.get("execution_receipt_path"),
        "changeset_path": promotion.get("changeset_path"),
        "commit_message": promotion.get("commit_message"),
        "head_sha": promotion.get("head_sha"),
        "committed_at": promotion.get("committed_at"),
        "pushed_at": promotion.get("pushed_at"),
        "pr_opened_at": promotion.get("pr_opened_at"),
    }


def promotion_status_summary(task: dict) -> str | None:
    summary = promotion_summary(task)
    status = str(summary.get("status") or "").strip()
    required = bool(summary.get("required"))
    pr_number = summary.get("pr_number")
    if not required and status == PROMOTION_STATUS_NOT_REQUIRED and pr_number in (None, ""):
        return None
    if pr_number not in (None, ""):
        return f"{status}#{pr_number}"
    return status or None


def legacy_promotion_projection(task: dict) -> dict[str, object]:
    ensure_task_promotion_defaults_without_meta(task)
    promotion = task["promotion"]
    legacy_status = promotion.get("status")
    if legacy_status == PROMOTION_STATUS_RECORDED:
        legacy_status = PROMOTION_STATUS_MERGED
    return {
        "status": legacy_status,
        "recorded_at": promotion.get("recorded_at"),
        "repo_full_name": promotion.get("repo_full_name"),
        "pr_number": promotion.get("pr_number"),
        "title": promotion.get("title"),
        "url": promotion.get("pr_url"),
        "head_branch": promotion.get("head_branch"),
        "base_branch": promotion.get("base_branch"),
        "head_sha": promotion.get("head_sha"),
        "merge_commit_sha": promotion.get("merge_commit_sha"),
        "merged_at": promotion.get("merged_at"),
        "merged_by": promotion.get("merged_by"),
        "merge_method": promotion.get("merge_method"),
        "receipt_path": promotion.get("receipt_path"),
        "changeset_path": promotion.get("changeset_path"),
        "parent_artifact_id": promotion.get("parent_artifact_id"),
        "parent_task_id": promotion.get("parent_task_id"),
    }


def classify_task_promotion_requirement(task: dict) -> tuple[bool, str]:
    task_type = str(task.get("type") or "").strip().lower()
    if task_type != "feature":
        return False, "non-feature tasks are not promotable by default"

    candidate_paths = _promotion_candidate_paths(task)
    if candidate_paths and all(_is_non_promotable_path(path) for path in candidate_paths):
        return False, "task only targets tests or internal planning artifacts"

    return True, "feature tasks are promotable by default"


def ensure_task_promotion_defaults_without_meta(task: dict) -> dict:
    defaults = default_task_promotion()
    if not isinstance(task.get("promotion"), dict):
        task["promotion"] = copy.deepcopy(defaults)
    promotion = task["promotion"]
    for key, value in defaults.items():
        promotion.setdefault(key, copy.deepcopy(value))
    return task


def _legacy_promotion(task: dict) -> dict[str, object]:
    meta = task.get("meta", {})
    if not isinstance(meta, dict):
        return {}
    legacy = meta.get("promotion")
    if not isinstance(legacy, dict):
        return {}
    return legacy


def _promotion_has_material_state(promotion: dict) -> bool:
    signal_keys = (
        "parent_artifact_id",
        "parent_task_id",
        "pr_number",
        "pr_url",
        "repo_full_name",
        "title",
        "head_sha",
        "merge_commit_sha",
        "merged_at",
        "merged_by",
        "merge_method",
        "recorded_at",
    )
    return any(_normalize_text_value(promotion.get(key)) is not None for key in signal_keys) or (
        isinstance(promotion.get("pr_number"), int) and promotion.get("pr_number") > 0
    )


def _should_auto_classify_task(task: dict) -> bool:
    meta = task.get("meta", {})
    if not isinstance(meta, dict):
        return False
    source_event_type = _normalize_text_value(meta.get("source_event_type"))
    if source_event_type == "conversation":
        return True
    source_context = meta.get("source_context")
    return isinstance(source_context, dict) and bool(source_context)


def _promotion_candidate_paths(task: dict) -> tuple[str, ...]:
    meta = task.get("meta", {})
    if not isinstance(meta, dict):
        return ()
    values: list[str] = []

    for key in ("owned_paths", "requested_adopt_paths"):
        raw = meta.get(key)
        if not isinstance(raw, list):
            continue
        for item in raw:
            normalized = _normalize_repo_path(item)
            if normalized and normalized not in values:
                values.append(normalized)

    adopted_changes = meta.get("adopted_changes")
    if isinstance(adopted_changes, dict):
        for key in ("paths", "requested_paths"):
            raw = adopted_changes.get(key)
            if not isinstance(raw, list):
                continue
            for item in raw:
                normalized = _normalize_repo_path(item)
                if normalized and normalized not in values:
                    values.append(normalized)

    return tuple(values)


def _is_non_promotable_path(path: str) -> bool:
    normalized = _normalize_repo_path(path)
    if normalized is None:
        return False
    return any(
        normalized == prefix.rstrip("/") or normalized.startswith(prefix)
        for prefix in NON_PROMOTABLE_PATH_PREFIXES
    )


def _coerce_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"true", "yes", "1"}:
            return True
        if lowered in {"false", "no", "0", ""}:
            return False
    return bool(value)


def _coerce_optional_bool(value: object) -> bool | None:
    if value in (None, ""):
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"true", "yes", "1"}:
            return True
        if lowered in {"false", "no", "0"}:
            return False
    return bool(value)


def _coalesce_text(*values: object) -> str | None:
    for value in values:
        normalized = _normalize_text_value(value)
        if normalized is not None:
            return normalized
    return None


def _coalesce_int(*values: object) -> int | None:
    for value in values:
        if value in (None, ""):
            continue
        try:
            normalized = int(value)
        except (TypeError, ValueError):
            continue
        if normalized > 0:
            return normalized
    return None


def _normalize_text_value(value: object | None) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip()
    return normalized or None


def _normalize_repo_path(value: object | None) -> str | None:
    normalized = _normalize_text_value(value)
    if normalized is None:
        return None
    return normalized.replace("\\", "/").lstrip("./")
