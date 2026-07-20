from __future__ import annotations

import re

from .design import sync_design_from_content


SECTION_PATTERN = re.compile(r"^##\s+(?P<title>.+?)\s*$", re.MULTILINE)
SUBSECTION_PATTERN = re.compile(r"^###\s+(?P<title>.+?)\s*$", re.MULTILINE)

PLACEHOLDER_VALUES = {
    "happy path 1",
    "happy path 2",
    "edge case 1",
    "edge case 2",
    "exception case 1",
    "exception case 2",
    "baseline behavior still works",
    "yes/no",
    "codex/claude/other",
    "n/a",
}


def sync_test_strategy_from_content(task: dict, content: str) -> dict:
    previous_strategy = task.get("test_strategy")
    previous_external = (
        previous_strategy.get("external_llm")
        if isinstance(previous_strategy, dict)
        and isinstance(previous_strategy.get("external_llm"), dict)
        else {}
    )
    parsed_external = _extract_external_llm(content)
    task["test_strategy"] = {
        "normal_cases": _extract_checklist_items(content, "Normal Cases"),
        "edge_cases": _extract_checklist_items(content, "Edge Cases"),
        "exception_cases": _extract_checklist_items(content, "Exception Cases"),
        "verification_methods": _extract_verification_mapping(content),
        "external_llm": _preserve_external_review_evidence(
            parsed_external,
            previous_external,
        ),
    }
    return sync_design_from_content(task, content)


_EXTERNAL_REVIEW_POLICY_FIELDS = ("required", "provider", "purpose", "trigger")
_EXTERNAL_REVIEW_EVIDENCE_FIELDS = (
    "status",
    "reviewer",
    "reviewed_at",
    "reviewed_head_sha",
    "scope_digest",
    "envelope_path",
    "envelope_digest",
    "envelope_size_bytes",
    "report_path",
    "report_digest",
    "report_size_bytes",
    "finding_count",
    "blocking_finding_count",
    "findings",
    "summary",
    "verification_binding",
)


def _preserve_external_review_evidence(parsed: dict, previous: dict) -> dict:
    if not parsed.get("required"):
        return parsed
    policy_unchanged = all(
        parsed.get(field) == previous.get(field)
        for field in _EXTERNAL_REVIEW_POLICY_FIELDS
    )
    if not policy_unchanged:
        return parsed
    for field in _EXTERNAL_REVIEW_EVIDENCE_FIELDS:
        if field in previous:
            parsed[field] = previous[field]
    return parsed


def _extract_checklist_items(content: str, subsection_title: str) -> list[dict]:
    block = _extract_subsection_block(content, subsection_title)
    items: list[dict] = []
    for line in block.splitlines():
        stripped = line.strip()
        if stripped.startswith("- [ ] "):
            name = stripped.removeprefix("- [ ] ").strip()
            if not _is_placeholder_value(name):
                items.append({"name": name, "checked": False})
        elif stripped.startswith(("- [x] ", "- [X] ")):
            name = stripped[6:].strip()
            if not _is_placeholder_value(name):
                items.append({"name": name, "checked": True})
    return items


def _extract_verification_mapping(content: str) -> list[dict]:
    block = _extract_section_block(content, "Verification Mapping")
    mappings: list[dict] = []
    for line in block.splitlines():
        stripped = line.strip()
        if not stripped.startswith("- "):
            continue
        payload = stripped[2:]
        if "->" not in payload:
            continue
        left, right = payload.split("->", 1)
        target = left.strip().strip("`")
        method = right.strip().strip("`")
        if target and method and not _is_placeholder_value(target):
            mappings.append({"target": target, "method": method})
    return mappings


def _extract_external_llm(content: str) -> dict:
    block = _extract_section_block(content, "External LLM Review")
    result = {
        "required": False,
        "provider": None,
        "purpose": None,
        "trigger": None,
        "status": "not_needed",
    }
    for line in block.splitlines():
        stripped = line.strip()
        if not stripped.startswith("- "):
            continue
        payload = stripped[2:]
        if ":" not in payload:
            continue
        key, value = payload.split(":", 1)
        key = key.strip().lower()
        value = value.strip().strip("`")
        if key == "required":
            normalized = value.lower()
            if normalized in {"yes", "true"}:
                result["required"] = True
                result["status"] = "pending"
            elif normalized in {"no", "false"}:
                result["required"] = False
                result["status"] = "not_needed"
        elif key == "provider" and value and value not in {"codex/claude/other", "n/a"}:
            result["provider"] = value
        elif (
            key == "purpose"
            and value
            and value != "n/a"
            and "adversarial review" not in value
            and "root-cause challenge" not in value
        ):
            result["purpose"] = value
        elif (
            key == "trigger"
            and value
            and value != "n/a"
            and "before close" not in value
            and "after verify failed twice" not in value
            and "after second failed audit" not in value
        ):
            result["trigger"] = value
    return result


def _is_placeholder_value(value: str) -> bool:
    return value.strip().strip("`").lower() in PLACEHOLDER_VALUES


def _extract_section_block(content: str, title: str) -> str:
    return _extract_block(content, SECTION_PATTERN, title)


def _extract_subsection_block(content: str, title: str) -> str:
    return _extract_block(content, SUBSECTION_PATTERN, title)


def _extract_block(content: str, pattern: re.Pattern[str], title: str) -> str:
    matches = list(pattern.finditer(content))
    for index, match in enumerate(matches):
        if match.group("title").strip().lower() != title.lower():
            continue
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(content)
        return content[start:end].strip()
    return ""


__all__ = [
    "PLACEHOLDER_VALUES",
    "SECTION_PATTERN",
    "SUBSECTION_PATTERN",
    "sync_test_strategy_from_content",
]
