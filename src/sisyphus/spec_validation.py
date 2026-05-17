from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import hashlib
import json
import re

from .config import SisyphusConfig
from .design import ensure_task_design_defaults
from .state import load_task_record, save_task_record, utc_now
from .strategy import sync_test_strategy_from_docs


SPEC_VALIDATION_REPORT = "artifacts/spec-validation/latest.json"
SPEC_VALIDATION_GATE_CODES = {
    "SPEC_VALIDATION_FAILED",
    "SPEC_VALIDATION_STALE",
    "SPEC_VALIDATION_MISSING",
}
SPEC_VALIDATION_SOURCES = {"spec_validation"}

SECTION_PATTERN = re.compile(r"^##\s+(?P<title>.+?)\s*$", re.MULTILINE)
CHECKLIST_PATTERN = re.compile(r"^-\s+\[[ xX]\]\s+(?P<item>.+?)\s*$", re.MULTILINE)
WAIVER_PATTERN = re.compile(
    r"^-\s*(?:rule\s*:\s*)?(?P<rule>[A-Z0-9_/-]+)\s*(?:->|:)\s*(?P<body>.+?)\s*$",
    re.IGNORECASE | re.MULTILINE,
)

PLACEHOLDER_FRAGMENTS = {
    "describe the problem",
    "describe what should be true",
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
}


@dataclass(slots=True)
class SpecValidationOutcome:
    task_id: str
    status: str
    stale: bool
    report: dict
    report_path: Path
    gates: list[dict]


def validate_task_spec(
    repo_root: Path,
    config: SisyphusConfig,
    task_id: str,
    *,
    persist: bool = True,
) -> SpecValidationOutcome:
    task, task_file = load_task_record(repo_root=repo_root, task_dir_name=config.task_dir, task_id=task_id)
    task_dir = task_file.parent
    task = sync_test_strategy_from_docs(task=task, task_dir=task_dir)
    ensure_task_design_defaults(task)
    report = build_spec_validation_report(task=task, task_dir=task_dir)
    report_path = task_dir / SPEC_VALIDATION_REPORT
    gates = spec_validation_gates(report, action="spec validation")
    outcome = SpecValidationOutcome(
        task_id=str(task["id"]),
        status=str(report["status"]),
        stale=False,
        report=report,
        report_path=report_path,
        gates=gates,
    )
    if persist:
        persist_spec_validation_report(task=task, task_file=task_file, outcome=outcome)
    return outcome


def build_spec_validation_report(*, task: dict, task_dir: Path) -> dict:
    docs = _load_docs(task, task_dir)
    findings: list[dict] = []
    findings.extend(_validate_required_docs(task, docs))
    findings.extend(_validate_required_sections(task, docs))
    findings.extend(_validate_placeholders(docs))
    findings.extend(_validate_acceptance_criteria(task, docs))
    findings.extend(_validate_scope(task))
    findings.extend(_validate_test_strategy(task, docs))
    findings.extend(_validate_design(task))
    findings.extend(_validate_external_llm(task))
    findings.extend(_validate_dependency_ordering(task))

    error_count = sum(1 for finding in findings if finding["severity"] == "error")
    warning_count = sum(1 for finding in findings if finding["severity"] == "warning")
    status = "failed" if error_count else "warning" if warning_count else "passed"
    return {
        "task_id": task.get("id"),
        "status": status,
        "checked_at": utc_now(),
        "source_fingerprint": compute_source_fingerprint(task=task, task_dir=task_dir),
        "summary": {
            "error_count": error_count,
            "warning_count": warning_count,
            "finding_count": len(findings),
        },
        "gate_codes": sorted({finding["code"] for finding in findings if finding["severity"] == "error"}),
        "findings": findings,
    }


def persist_spec_validation_report(*, task: dict, task_file: Path, outcome: SpecValidationOutcome) -> None:
    report_path = outcome.report_path
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(outcome.report, indent=2) + "\n", encoding="utf-8")
    task["spec_validation"] = {
        "status": outcome.status,
        "checked_at": outcome.report.get("checked_at"),
        "report_path": str(Path(SPEC_VALIDATION_REPORT)),
        "source_fingerprint": outcome.report.get("source_fingerprint"),
        "error_count": outcome.report.get("summary", {}).get("error_count", 0),
        "warning_count": outcome.report.get("summary", {}).get("warning_count", 0),
    }
    save_task_record(task_file=task_file, task=task)


def load_spec_validation_report(task_dir: Path) -> dict | None:
    report_path = task_dir / SPEC_VALIDATION_REPORT
    if not report_path.exists():
        return None
    try:
        return json.loads(report_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def collect_spec_validation_gates(
    *,
    task: dict,
    task_dir: Path,
    action: str,
    require_existing_report: bool = False,
    persist: bool = True,
) -> list[dict]:
    existing = load_spec_validation_report(task_dir)
    if require_existing_report and existing is None:
        return [_gate("SPEC_VALIDATION_MISSING", f"task spec must be validated before {action}")]
    stale = existing is not None and existing.get("source_fingerprint") != compute_source_fingerprint(task=task, task_dir=task_dir)
    if require_existing_report and stale:
        return [_gate("SPEC_VALIDATION_STALE", f"task spec validation report is stale before {action}")]

    report = existing
    if report is None or stale or not require_existing_report:
        report = build_spec_validation_report(task=task, task_dir=task_dir)
        if persist:
            report_path = task_dir / SPEC_VALIDATION_REPORT
            report_path.parent.mkdir(parents=True, exist_ok=True)
            report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
            task["spec_validation"] = {
                "status": report.get("status"),
                "checked_at": report.get("checked_at"),
                "report_path": str(Path(SPEC_VALIDATION_REPORT)),
                "source_fingerprint": report.get("source_fingerprint"),
                "error_count": report.get("summary", {}).get("error_count", 0),
                "warning_count": report.get("summary", {}).get("warning_count", 0),
            }
    return spec_validation_gates(report, action=action)


def spec_validation_gates(report: dict, *, action: str) -> list[dict]:
    findings = [finding for finding in report.get("findings", []) if finding.get("severity") == "error"]
    if not findings:
        return []
    preview = "; ".join(f"{finding['code']}: {finding['message']}" for finding in findings[:3])
    if len(findings) > 3:
        preview += f"; +{len(findings) - 3} more"
    return [_gate("SPEC_VALIDATION_FAILED", f"task spec validation failed before {action}: {preview}")]


def compute_source_fingerprint(*, task: dict, task_dir: Path) -> str:
    payload: list[dict] = []
    for key in _required_doc_keys(task):
        relative_path = str(task.get("docs", {}).get(key) or "")
        doc_path = task_dir / relative_path if relative_path else None
        if not relative_path or doc_path is None or not doc_path.exists():
            payload.append({"key": key, "path": relative_path, "sha256": None})
            continue
        payload.append(
            {
                "key": key,
                "path": relative_path,
                "sha256": hashlib.sha256(doc_path.read_bytes()).hexdigest(),
            }
        )
    payload.append({"key": "type", "value": task.get("type")})
    payload.append({"key": "owned_paths", "value": task.get("meta", {}).get("owned_paths", [])})
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()


def _load_docs(task: dict, task_dir: Path) -> dict[str, dict]:
    docs: dict[str, dict] = {}
    for key in _required_doc_keys(task):
        relative_path = str(task.get("docs", {}).get(key) or "")
        doc_path = task_dir / relative_path if relative_path else None
        content = ""
        exists = False
        if doc_path is not None and doc_path.exists():
            content = doc_path.read_text(encoding="utf-8")
            exists = True
        docs[key] = {
            "key": key,
            "relative_path": relative_path,
            "exists": exists,
            "content": content,
            "sections": _sections(content),
        }
    return docs


def _required_doc_keys(task: dict) -> list[str]:
    if task.get("type") == "issue":
        return ["brief", "repro", "fix_plan"]
    return ["brief", "plan"]


def _validate_required_docs(task: dict, docs: dict[str, dict]) -> list[dict]:
    findings: list[dict] = []
    for key in _required_doc_keys(task):
        doc = docs.get(key, {})
        if not doc.get("relative_path"):
            findings.append(_finding("REQUIRED_DOC_MISSING", "error", "docs", f"{key} document is missing from task metadata", key))
        elif not doc.get("exists"):
            findings.append(_finding("REQUIRED_DOC_MISSING", "error", "docs", f"{doc.get('relative_path')} does not exist", key))
    return findings


def _validate_required_sections(task: dict, docs: dict[str, dict]) -> list[dict]:
    required = {
        "brief": (
            ["symptom", "expected behavior", "impact"]
            if task.get("type") == "issue"
            else ["problem", "desired outcome", "acceptance criteria", "constraints"]
        ),
        "plan": ["implementation plan", "risks", "design evaluation", "design artifacts", "test strategy", "verification mapping", "external llm review"],
        "repro": ["preconditions", "repro steps", "observed result", "expected result", "regression test target"],
        "fix_plan": ["root cause hypothesis", "fix strategy", "design evaluation", "design artifacts", "test strategy", "verification mapping", "external llm review"],
    }
    findings: list[dict] = []
    for key, expected_sections in required.items():
        if key not in docs:
            continue
        sections = docs[key].get("sections", {})
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
    return findings


def _validate_placeholders(docs: dict[str, dict]) -> list[dict]:
    findings: list[dict] = []
    for key, doc in docs.items():
        content = str(doc.get("content") or "").lower()
        for fragment in sorted(PLACEHOLDER_FRAGMENTS):
            if fragment in content:
                findings.append(
                    _finding(
                        "PLACEHOLDER_TEXT",
                        "error",
                        "docs",
                        f"{doc.get('relative_path')} still contains generated placeholder text: {fragment}",
                        key,
                    )
                )
                break
    return findings


def _validate_acceptance_criteria(task: dict, docs: dict[str, dict]) -> list[dict]:
    brief = docs.get("brief", {})
    section = str(brief.get("sections", {}).get("acceptance criteria") or "")
    items = [match.group("item").strip() for match in CHECKLIST_PATTERN.finditer(section)]
    concrete = [item for item in items if not _is_placeholder(item)]
    if task.get("type") == "feature" and not concrete:
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
    return []


def _validate_scope(task: dict) -> list[dict]:
    owned_paths = task.get("meta", {}).get("owned_paths")
    if isinstance(owned_paths, list) and any(str(path).strip() for path in owned_paths):
        return []
    return [
        _finding(
            "SCOPE_UNCLEAR",
            "warning",
            "task",
            "task has no owned paths; keep implementation scope explicit in review",
            None,
            remediation="Set owned_paths for broad lifecycle changes or state scope directly in the task docs.",
        )
    ]


def _validate_test_strategy(task: dict, docs: dict[str, dict]) -> list[dict]:
    strategy = task.get("test_strategy", {})
    findings: list[dict] = []
    coverage_keys = [
        ("normal_cases", "normal cases"),
        ("edge_cases", "edge cases"),
        ("exception_cases", "exception cases"),
    ]
    has_coverage_waiver = _has_waiver(docs, "COVERAGE_REQUIRED")
    for strategy_key, label in coverage_keys:
        if not strategy.get(strategy_key) and not has_coverage_waiver:
            findings.append(
                _finding(
                    "COVERAGE_REQUIRED",
                    "error",
                    "strategy",
                    f"test strategy must define at least one {label} item",
                    "plan" if task.get("type") == "feature" else "fix_plan",
                    section=label,
                )
            )

    methods = list(strategy.get("verification_methods") or [])
    if not methods and not _has_waiver(docs, "VERIFICATION_MAPPING_REQUIRED"):
        findings.append(
            _finding(
                "VERIFICATION_MAPPING_REQUIRED",
                "error",
                "strategy",
                "verification mapping must define at least one method",
                "plan" if task.get("type") == "feature" else "fix_plan",
                section="verification mapping",
            )
        )
        return findings

    mapped_targets = {_normalize_target(item.get("target")) for item in methods if isinstance(item, dict)}
    coverage_targets = {
        _normalize_target(item.get("name"))
        for key, _label in coverage_keys
        for item in strategy.get(key, [])
        if isinstance(item, dict)
    }
    missing_targets = sorted(target for target in coverage_targets if target and target not in mapped_targets)
    if missing_targets:
        findings.append(
            _finding(
                "VERIFICATION_MAPPING_INCOMPLETE",
                "error",
                "strategy",
                f"verification mapping is missing coverage targets: {', '.join(missing_targets[:3])}",
                "plan" if task.get("type") == "feature" else "fix_plan",
                section="verification mapping",
            )
        )

    for method in methods:
        if not isinstance(method, dict):
            continue
        method_text = str(method.get("method") or "").strip()
        if not method_text or _is_placeholder(method_text):
            findings.append(
                _finding(
                    "VERIFICATION_METHOD_PLACEHOLDER",
                    "error",
                    "strategy",
                    "verification mapping method must name a concrete command, test, artifact, or review trigger",
                    "plan" if task.get("type") == "feature" else "fix_plan",
                    section="verification mapping",
                )
            )
            break
    return findings


def _validate_design(task: dict) -> list[dict]:
    ensure_task_design_defaults(task)
    design = task.get("design", {})
    findings: list[dict] = []
    layer_impact = design.get("layer_impact")
    mode = design.get("mode")
    if layer_impact in {"layer-adding", "layer-reshaping"} and mode == "none":
        findings.append(
            _finding(
                "DESIGN_MODE_INSUFFICIENT",
                "error",
                "design",
                "layer-adding or layer-reshaping work cannot use design_mode=none",
                "plan" if task.get("type") == "feature" else "fix_plan",
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
                "plan" if task.get("type") == "feature" else "fix_plan",
                section="design artifacts",
            )
        )
    return findings


def _validate_external_llm(task: dict) -> list[dict]:
    external_llm = task.get("test_strategy", {}).get("external_llm", {})
    if not external_llm.get("required"):
        return []
    missing = [
        key
        for key in ("provider", "purpose", "trigger")
        if not str(external_llm.get(key) or "").strip()
    ]
    if not missing:
        return []
    return [
        _finding(
            "EXTERNAL_LLM_POLICY_MISSING",
            "error",
            "strategy",
            f"external LLM review policy is missing: {', '.join(missing)}",
            "plan" if task.get("type") == "feature" else "fix_plan",
            section="external llm review",
        )
    ]


def _validate_dependency_ordering(task: dict) -> list[dict]:
    prerequisites = task.get("meta", {}).get("prerequisite_task_ids")
    if not prerequisites:
        return []
    if not isinstance(prerequisites, list):
        return [
            _finding(
                "PREREQUISITE_FORMAT_INVALID",
                "warning",
                "task",
                "prerequisite_task_ids should be a list of task ids",
                None,
            )
        ]
    return []


def _sections(content: str) -> dict[str, str]:
    matches = list(SECTION_PATTERN.finditer(content))
    sections: dict[str, str] = {}
    for index, match in enumerate(matches):
        title = match.group("title").strip().lower()
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(content)
        sections[title] = content[start:end].strip()
    return sections


def _has_waiver(docs: dict[str, dict], code: str) -> bool:
    for doc in docs.values():
        for section_name in ("validation waivers", "waivers"):
            block = str(doc.get("sections", {}).get(section_name) or "")
            for match in WAIVER_PATTERN.finditer(block):
                if match.group("rule").strip().upper().replace("-", "_") != code:
                    continue
                body = match.group("body").strip().lower()
                if "reason" in body and "scope" in body:
                    return True
    return False


def _normalize_target(value: object) -> str:
    return str(value or "").strip().strip("`").lower()


def _is_placeholder(value: str) -> bool:
    normalized = value.strip().strip("`").lower()
    return normalized in PLACEHOLDER_FRAGMENTS


def _finding(
    code: str,
    severity: str,
    source: str,
    message: str,
    doc: str | None,
    *,
    section: str | None = None,
    remediation: str | None = None,
) -> dict:
    finding = {
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


def _gate(code: str, message: str) -> dict:
    return {
        "code": code,
        "message": message,
        "blocking": True,
        "source": "spec_validation",
        "created_at": utc_now(),
    }
