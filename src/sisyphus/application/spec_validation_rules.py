from __future__ import annotations

from collections.abc import Mapping
import re

from ..domain.task.design import ensure_task_design_defaults


SECTION_PATTERN = re.compile(r"^##\s+(?P<title>.+?)\s*$", re.MULTILINE)
CHECKLIST_PATTERN = re.compile(r"^-\s+\[[ xX]\]\s+(?P<item>.+?)\s*$", re.MULTILINE)
WAIVER_PATTERN = re.compile(
    r"^-\s*(?:rule\s*:\s*)?(?P<rule>[A-Z0-9_/-]+)\s*(?:->|:)\s*(?P<body>.+?)\s*$",
    re.IGNORECASE | re.MULTILINE,
)
TASK_ID_PATTERN = re.compile(r"^TF-\d{8}-(?:feature|issue)-[a-z0-9][a-z0-9-]*$")

PLACEHOLDER_FRAGMENTS = {
    "describe the problem",
    "describe what is broken",
    "describe what should be true",
    "describe what should happen",
    "describe the observed result",
    "describe the expected result",
    "describe the test",
    "criterion 1",
    "criterion 2",
    "criterion 3",
    "constraint 1",
    "constraint 2",
    "hypothesis 1",
    "risk 1",
    "risk 2",
    "step 1",
    "step 2",
    "step 3",
    "happy path 1",
    "edge case 1",
    "exception case 1",
    "baseline behavior still works",
    "yes/no",
    "codex/claude/other",
    "none | light | full",
    "low/medium/high",
    "layer-preserving | layer-touching | layer-reshaping | layer-adding",
    "none | connection_diagram, sequence_diagram, boundary_note",
    "existing contract only / crosses a few modules / introduces a new layer",
    "the repository behavior matches the requested conversation outcome",
    "the requested workflow is implemented or corrected",
    "the task docs reflect the actual implementation and verification scope",
    "verification notes are ready to be updated after implementation",
    "requested conversation workflow succeeds",
    "minimal valid input still behaves predictably",
    "unexpected failure surfaces an actionable error",
}

PLACEHOLDER_PREFIXES = {
    "describe the problem",
    "describe what is broken",
    "describe what should be true",
    "describe what should happen",
    "describe the observed result",
    "describe the expected result",
    "describe the test",
    "inspect the current code path related to:",
    "implement the requested behavior for:",
}


def evaluate_spec_findings(
    *,
    task: dict,
    docs: dict[str, dict[str, object]],
    prerequisites: Mapping[str, object],
) -> list[dict[str, object]]:
    findings: list[dict[str, object]] = []
    findings.extend(_validate_required_docs(task, docs))
    findings.extend(_validate_required_sections(task, docs))
    findings.extend(_validate_placeholders(docs))
    findings.extend(_validate_acceptance_criteria(task, docs))
    findings.extend(_validate_scope(task, docs))
    findings.extend(_validate_test_strategy(task, docs))
    findings.extend(_validate_design(task))
    findings.extend(_validate_external_llm(task))
    findings.extend(_validate_dependency_ordering(task, prerequisites))
    return findings


def required_doc_keys(task: Mapping[str, object]) -> tuple[str, ...]:
    if task.get("type") == "issue":
        return ("brief", "repro", "fix_plan")
    return ("brief", "plan")


def parse_sections(content: str) -> dict[str, str]:
    matches = list(SECTION_PATTERN.finditer(content))
    sections: dict[str, str] = {}
    for index, match in enumerate(matches):
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(content)
        sections[match.group("title").strip().lower()] = content[start:end].strip()
    return sections


def prerequisite_task_ids_to_load(task: Mapping[str, object]) -> tuple[str, ...]:
    meta = task.get("meta") if isinstance(task.get("meta"), dict) else {}
    raw_ids = meta.get("prerequisite_task_ids")
    if not isinstance(raw_ids, list):
        return ()
    return tuple(
        task_id
        for value in raw_ids
        if TASK_ID_PATTERN.fullmatch(task_id := str(value).strip())
    )


def _validate_required_docs(
    task: dict,
    docs: dict[str, dict[str, object]],
) -> list[dict[str, object]]:
    findings: list[dict[str, object]] = []
    for key in required_doc_keys(task):
        doc = docs.get(key, {})
        relative_path = str(doc.get("relative_path") or "")
        if not relative_path:
            findings.append(
                _finding(
                    "REQUIRED_DOC_MISSING",
                    "error",
                    "docs",
                    f"{key} document is missing from task metadata",
                    key,
                )
            )
        elif not doc.get("safe"):
            findings.append(
                _finding(
                    "DOC_PATH_INVALID",
                    "error",
                    "docs",
                    f"{relative_path} must stay inside the task directory",
                    key,
                )
            )
        elif not doc.get("exists"):
            findings.append(
                _finding(
                    "REQUIRED_DOC_MISSING",
                    "error",
                    "docs",
                    f"{relative_path} does not exist",
                    key,
                )
            )
    return findings


def _validate_required_sections(
    task: dict,
    docs: dict[str, dict[str, object]],
) -> list[dict[str, object]]:
    required = {
        "brief": (
            ["symptom", "expected behavior", "impact"]
            if task.get("type") == "issue"
            else ["problem", "desired outcome", "acceptance criteria", "constraints"]
        ),
        "plan": [
            "implementation plan",
            "risks",
            "design evaluation",
            "design artifacts",
            "test strategy",
            "verification mapping",
            "external llm review",
        ],
        "repro": [
            "preconditions",
            "repro steps",
            "observed result",
            "expected result",
            "regression test target",
        ],
        "fix_plan": [
            "root cause hypothesis",
            "fix strategy",
            "design evaluation",
            "design artifacts",
            "test strategy",
            "verification mapping",
            "external llm review",
        ],
    }
    findings: list[dict[str, object]] = []
    for key, expected_sections in required.items():
        if key not in docs or not docs[key].get("exists"):
            continue
        sections = docs[key].get("sections")
        if not isinstance(sections, dict):
            sections = {}
        for section in expected_sections:
            if section not in sections:
                findings.append(
                    _finding(
                        "REQUIRED_SECTION_MISSING",
                        "error",
                        "docs",
                        f"{docs[key].get('relative_path')} must include `{section}`",
                        key,
                        section=section,
                    )
                )
            elif not str(sections.get(section) or "").strip():
                findings.append(
                    _finding(
                        "REQUIRED_SECTION_EMPTY",
                        "error",
                        "docs",
                        f"{docs[key].get('relative_path')} section `{section}` is empty",
                        key,
                        section=section,
                    )
                )
    return findings


def _validate_placeholders(
    docs: dict[str, dict[str, object]],
) -> list[dict[str, object]]:
    findings: list[dict[str, object]] = []
    for key, doc in docs.items():
        content = str(doc.get("content") or "")
        fragment = next(
            (
                placeholder
                for line in content.splitlines()
                if (placeholder := _placeholder_line_value(line)) is not None
            ),
            None,
        )
        if fragment:
            findings.append(
                _finding(
                    "PLACEHOLDER_TEXT",
                    "error",
                    "docs",
                    f"{doc.get('relative_path')} still contains generated placeholder text: {fragment}",
                    key,
                )
            )
    return findings


def _validate_acceptance_criteria(
    task: dict,
    docs: dict[str, dict[str, object]],
) -> list[dict[str, object]]:
    if task.get("type") != "feature":
        return []
    sections = docs.get("brief", {}).get("sections")
    block = (
        str(sections.get("acceptance criteria") or "")
        if isinstance(sections, dict)
        else ""
    )
    items = [match.group("item").strip() for match in CHECKLIST_PATTERN.finditer(block)]
    if any(item and not _is_placeholder(item) for item in items):
        return []
    return [
        _finding(
            "ACCEPTANCE_CRITERIA_MISSING",
            "error",
            "docs",
            "feature task requires at least one concrete acceptance criterion",
            "brief",
            section="acceptance criteria",
        )
    ]


def _validate_scope(
    task: dict,
    docs: dict[str, dict[str, object]],
) -> list[dict[str, object]]:
    meta = task.get("meta") if isinstance(task.get("meta"), dict) else {}
    owned_paths = meta.get("owned_paths")
    if isinstance(owned_paths, list) and any(str(path).strip() for path in owned_paths):
        return []
    for doc in docs.values():
        sections = doc.get("sections")
        if isinstance(sections, dict) and any(
            str(sections.get(name) or "").strip() for name in ("scope", "out of scope")
        ):
            return []
    return [
        _finding(
            "SCOPE_UNCLEAR",
            "warning",
            "task",
            "task has no owned paths or explicit scope section",
            None,
            remediation="Set owned_paths or add a concrete Scope section.",
        )
    ]


def _validate_test_strategy(
    task: dict,
    docs: dict[str, dict[str, object]],
) -> list[dict[str, object]]:
    strategy = task.get("test_strategy") if isinstance(task.get("test_strategy"), dict) else {}
    findings: list[dict[str, object]] = []
    coverage_keys = (
        ("normal_cases", "normal cases"),
        ("edge_cases", "edge cases"),
        ("exception_cases", "exception cases"),
    )
    if not _has_waiver(docs, "COVERAGE_REQUIRED"):
        for strategy_key, label in coverage_keys:
            if not strategy.get(strategy_key):
                findings.append(
                    _finding(
                        "COVERAGE_REQUIRED",
                        "error",
                        "strategy",
                        f"test strategy must define at least one {label} item",
                        _plan_doc_key(task),
                        section=label,
                    )
                )

    methods = list(strategy.get("verification_methods") or [])
    if not methods:
        if not _has_waiver(docs, "VERIFICATION_MAPPING_REQUIRED"):
            findings.append(
                _finding(
                    "VERIFICATION_MAPPING_REQUIRED",
                    "error",
                    "strategy",
                    "verification mapping must define at least one method",
                    _plan_doc_key(task),
                    section="verification mapping",
                )
            )
        return findings

    mapped_targets = {
        _normalize_target(item.get("target")) for item in methods if isinstance(item, dict)
    }
    coverage_targets = {
        _normalize_target(item.get("name"))
        for key, _ in coverage_keys
        for item in strategy.get(key, [])
        if isinstance(item, dict)
    }
    missing_targets = sorted(
        target for target in coverage_targets if target and target not in mapped_targets
    )
    if missing_targets and not _has_waiver(docs, "VERIFICATION_MAPPING_REQUIRED"):
        findings.append(
            _finding(
                "VERIFICATION_MAPPING_INCOMPLETE",
                "error",
                "strategy",
                "verification mapping is missing coverage targets: "
                + ", ".join(missing_targets[:3]),
                _plan_doc_key(task),
                section="verification mapping",
            )
        )

    for method in methods:
        method_text = (
            str(method.get("method") or "").strip() if isinstance(method, dict) else ""
        )
        if not method_text or _is_placeholder(method_text):
            findings.append(
                _finding(
                    "VERIFICATION_METHOD_PLACEHOLDER",
                    "error",
                    "strategy",
                    "verification mapping method must name a concrete command, test, artifact, or review trigger",
                    _plan_doc_key(task),
                    section="verification mapping",
                )
            )
            break
    return findings


def _validate_design(task: dict) -> list[dict[str, object]]:
    ensure_task_design_defaults(task)
    design = task["design"]
    findings: list[dict[str, object]] = []
    if (
        design.get("layer_impact") in {"layer-adding", "layer-reshaping"}
        and design.get("mode") == "none"
    ):
        findings.append(
            _finding(
                "DESIGN_MODE_INSUFFICIENT",
                "error",
                "design",
                "layer-adding or layer-reshaping work cannot use design_mode=none",
                _plan_doc_key(task),
                section="design evaluation",
            )
        )
    missing_artifacts = [
        artifact
        for artifact in design.get("required_artifacts", [])
        if not design.get("artifacts", {}).get(artifact)
    ]
    if missing_artifacts:
        findings.append(
            _finding(
                "DESIGN_ARTIFACT_REQUIRED",
                "error",
                "design",
                f"required design artifacts are missing: {', '.join(missing_artifacts)}",
                _plan_doc_key(task),
                section="design artifacts",
            )
        )
    return findings


def _validate_external_llm(task: dict) -> list[dict[str, object]]:
    strategy = task.get("test_strategy") if isinstance(task.get("test_strategy"), dict) else {}
    external = (
        strategy.get("external_llm")
        if isinstance(strategy.get("external_llm"), dict)
        else {}
    )
    if not external.get("required"):
        return []
    missing = [
        key for key in ("provider", "purpose", "trigger") if not str(external.get(key) or "").strip()
    ]
    if not missing:
        return []
    return [
        _finding(
            "EXTERNAL_LLM_POLICY_MISSING",
            "error",
            "strategy",
            f"external LLM review policy is missing: {', '.join(missing)}",
            _plan_doc_key(task),
            section="external llm review",
        )
    ]


def _validate_dependency_ordering(
    task: dict,
    prerequisites: Mapping[str, object],
) -> list[dict[str, object]]:
    meta = task.get("meta") if isinstance(task.get("meta"), dict) else {}
    raw_ids = meta.get("prerequisite_task_ids")
    if raw_ids in (None, []):
        return []
    if not isinstance(raw_ids, list):
        return [
            _finding(
                "PREREQUISITE_FORMAT_INVALID",
                "warning",
                "task",
                "prerequisite_task_ids should be a list of task ids",
                None,
            )
        ]
    findings: list[dict[str, object]] = []
    for raw_task_id in raw_ids:
        prerequisite_id = str(raw_task_id).strip()
        if not TASK_ID_PATTERN.fullmatch(prerequisite_id):
            findings.append(
                _finding(
                    "PREREQUISITE_FORMAT_INVALID",
                    "warning",
                    "task",
                    f"invalid prerequisite task id: {prerequisite_id or '<empty>'}",
                    None,
                )
            )
            continue
        if prerequisite_id not in prerequisites:
            findings.append(
                _finding(
                    "PREREQUISITE_NOT_FOUND",
                    "warning",
                    "task",
                    f"prerequisite task is not readable: {prerequisite_id}",
                    None,
                )
            )
            continue
        prerequisite = prerequisites[prerequisite_id]
        if not isinstance(prerequisite, dict):
            findings.append(
                _finding(
                    "PREREQUISITE_NOT_FOUND",
                    "warning",
                    "task",
                    f"prerequisite task record is invalid: {prerequisite_id}",
                    None,
                )
            )
            continue
        promotion = (
            prerequisite.get("promotion")
            if isinstance(prerequisite.get("promotion"), dict)
            else {}
        )
        ready = (
            prerequisite.get("status") == "closed"
            or promotion.get("status") == "promotion_recorded"
            or (
                prerequisite.get("plan_status") == "approved"
                and prerequisite.get("spec_status") == "frozen"
            )
        )
        if not ready:
            findings.append(
                _finding(
                    "PREREQUISITE_NOT_READY",
                    "warning",
                    "task",
                    f"prerequisite task is not approved and frozen or merged: {prerequisite_id}",
                    None,
                )
            )
    return findings


def _has_waiver(docs: dict[str, dict[str, object]], code: str) -> bool:
    for doc in docs.values():
        sections = doc.get("sections")
        if not isinstance(sections, dict):
            continue
        for section_name in ("validation waivers", "waivers"):
            block = str(sections.get(section_name) or "")
            for match in WAIVER_PATTERN.finditer(block):
                rule = match.group("rule").strip().upper().replace("-", "_")
                body = match.group("body").strip().lower()
                if rule == code and "reason" in body and "scope" in body:
                    return True
    return False


def _plan_doc_key(task: dict) -> str:
    return "fix_plan" if task.get("type") == "issue" else "plan"


def _normalize_target(value: object) -> str:
    normalized = str(value or "").replace("`", "").strip().lower()
    return " ".join(normalized.split())


def _is_placeholder(value: str) -> bool:
    normalized = value.strip().strip("`").lower()
    return normalized in PLACEHOLDER_FRAGMENTS


def _placeholder_line_value(raw_line: str) -> str | None:
    value = raw_line.strip()
    if not value:
        return None
    value = re.sub(r"^\d+\.\s+", "", value)
    value = re.sub(r"^-\s+", "", value)
    value = re.sub(r"^\[[ xX]\]\s+", "", value)
    if ":" in value:
        label, candidate = value.split(":", 1)
        if label.strip().lower() in {
            "design mode",
            "decision reason",
            "confidence",
            "layer impact",
            "required design artifacts",
            "required",
            "provider",
            "purpose",
            "trigger",
        }:
            value = candidate
    normalized = value.strip().strip("`").rstrip(".").strip().lower()
    if normalized in PLACEHOLDER_FRAGMENTS:
        return normalized
    if any(normalized.startswith(prefix) for prefix in PLACEHOLDER_PREFIXES):
        return normalized
    return None


def _finding(
    code: str,
    severity: str,
    source: str,
    message: str,
    doc: str | None,
    *,
    section: str | None = None,
    remediation: str | None = None,
) -> dict[str, object]:
    finding: dict[str, object] = {
        "code": code,
        "severity": severity,
        "source": source,
        "message": message,
        "doc": doc,
    }
    if section:
        finding["section"] = section
    if remediation:
        finding["remediation"] = remediation
    return finding


__all__ = [
    "evaluate_spec_findings",
    "parse_sections",
    "prerequisite_task_ids_to_load",
    "required_doc_keys",
]
