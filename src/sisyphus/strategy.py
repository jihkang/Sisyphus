from __future__ import annotations

from pathlib import Path
import re

from .design import sync_design_from_docs


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


def sync_test_strategy_from_docs(task: dict, task_dir: Path) -> dict:
    source_name = "PLAN.md" if task["type"] == "feature" else "FIX_PLAN.md"
    source_path = task_dir / source_name
    if not source_path.exists():
        return task

    content = source_path.read_text(encoding="utf-8")
    strategy = {
        "normal_cases": _extract_checklist_items(content, "Normal Cases"),
        "edge_cases": _extract_checklist_items(content, "Edge Cases"),
        "exception_cases": _extract_checklist_items(content, "Exception Cases"),
        "verification_methods": _extract_verification_mapping(content),
        "external_llm": _extract_external_llm(content),
    }
    task["test_strategy"] = strategy
    task = sync_design_from_docs(task=task, task_dir=task_dir, source_name=source_name)
    return task


def _extract_checklist_items(content: str, subsection_title: str) -> list[dict]:
    block = _extract_subsection_block(content, subsection_title)
    items: list[dict] = []
    for line in block.splitlines():
        stripped = line.strip()
        if stripped.startswith("- [ ] "):
            name = stripped.removeprefix("- [ ] ").strip()
            if _is_placeholder_value(name):
                continue
            items.append({"name": name, "checked": False})
        elif stripped.startswith("- [x] ") or stripped.startswith("- [X] "):
            name = stripped[6:].strip()
            if _is_placeholder_value(name):
                continue
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
        elif key == "purpose" and value and value != "n/a" and "adversarial review" not in value and "root-cause challenge" not in value:
            result["purpose"] = value
        elif key == "trigger" and value and value != "n/a" and "before close" not in value and "after verify failed twice" not in value and "after second failed audit" not in value:
            result["trigger"] = value
    return result


def _is_placeholder_value(value: str) -> bool:
    normalized = value.strip().strip("`").lower()
    return normalized in PLACEHOLDER_VALUES


def _extract_section_block(content: str, title: str) -> str:
    return _extract_block(content, SECTION_PATTERN, title, SECTION_PATTERN)


def _extract_subsection_block(content: str, title: str) -> str:
    return _extract_block(content, SUBSECTION_PATTERN, title, SUBSECTION_PATTERN)


def _extract_block(content: str, pattern: re.Pattern[str], title: str, boundary_pattern: re.Pattern[str]) -> str:
    matches = list(pattern.finditer(content))
    for index, match in enumerate(matches):
        if match.group("title").strip().lower() != title.lower():
            continue
        start = match.end()
        end = len(content)
        for next_match in matches[index + 1 :]:
            end = next_match.start()
            break
        return content[start:end].strip()
    return ""
