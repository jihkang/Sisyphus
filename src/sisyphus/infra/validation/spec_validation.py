from __future__ import annotations

from pathlib import Path
import hashlib
import json
import re

from ...application.contracts.spec_validation import (
    SPEC_VALIDATION_GATE_CODES,
    SPEC_VALIDATION_SOURCES,
)
from ...application.planning_records import dedupe_gate_records, make_gate_record
from ...application.results.planning import SpecValidationOutcome
from ...domain.task.design import ensure_task_design_defaults
from ...shared.clock import utc_now
from ..config.loader import SisyphusConfig
from ..documents.task_strategy import sync_test_strategy_from_docs
from ..persistence.json_store import read_json_file, write_json_file
from ..persistence.task_repository import load_task_record, save_task_record


SPEC_VALIDATION_REPORT = "artifacts/spec-validation/latest.json"
SPEC_VALIDATION_SCHEMA_VERSION = "sisyphus.spec_validation.v1"

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


def validate_task_spec(
    repo_root: Path,
    config: SisyphusConfig,
    task_id: str,
    *,
    persist: bool = True,
) -> SpecValidationOutcome:
    task, task_file = load_task_record(
        repo_root=repo_root,
        task_dir_name=config.task_dir,
        task_id=task_id,
    )
    task_dir = task_file.parent
    task = sync_test_strategy_from_docs(task=task, task_dir=task_dir)
    ensure_task_design_defaults(task)
    report = build_spec_validation_report(task=task, task_dir=task_dir)
    report_path = task_dir / SPEC_VALIDATION_REPORT
    outcome = SpecValidationOutcome(
        task_id=str(task["id"]),
        status=str(report["status"]),
        stale=False,
        report=report,
        report_path=report_path,
        gates=spec_validation_gates(report, action="spec validation"),
    )
    if persist:
        persist_spec_validation_report(task=task, task_file=task_file, outcome=outcome)
    return outcome


def build_spec_validation_report(*, task: dict, task_dir: Path) -> dict[str, object]:
    docs = _load_docs(task, task_dir)
    findings: list[dict[str, object]] = []
    findings.extend(_validate_required_docs(task, docs))
    findings.extend(_validate_required_sections(task, docs))
    findings.extend(_validate_placeholders(docs))
    findings.extend(_validate_acceptance_criteria(task, docs))
    findings.extend(_validate_scope(task, docs))
    findings.extend(_validate_test_strategy(task, docs))
    findings.extend(_validate_design(task))
    findings.extend(_validate_external_llm(task))
    findings.extend(_validate_dependency_ordering(task, task_dir))

    error_count = sum(finding["severity"] == "error" for finding in findings)
    warning_count = sum(finding["severity"] == "warning" for finding in findings)
    status = "failed" if error_count else "warning" if warning_count else "passed"
    return {
        "schema_version": SPEC_VALIDATION_SCHEMA_VERSION,
        "task_id": task.get("id"),
        "status": status,
        "checked_at": utc_now(),
        "source_fingerprint": compute_source_fingerprint(task=task, task_dir=task_dir),
        "summary": {
            "error_count": error_count,
            "warning_count": warning_count,
            "finding_count": len(findings),
        },
        "gate_codes": sorted(
            {
                str(finding["code"])
                for finding in findings
                if finding["severity"] == "error"
            }
        ),
        "findings": findings,
    }


def persist_spec_validation_report(
    *,
    task: dict,
    task_file: Path,
    outcome: SpecValidationOutcome,
) -> None:
    write_json_file(outcome.report_path, outcome.report)
    _record_validation_state(task, outcome.report, stale=False)
    task.setdefault("meta", {})["spec_validation_required"] = True
    task["gates"] = dedupe_gate_records(
        [
            gate
            for gate in task.get("gates", [])
            if gate.get("source") != "spec_validation"
        ]
        + outcome.gates
    )
    save_task_record(task_file=task_file, task=task)


def load_spec_validation_report(task_dir: Path) -> dict[str, object] | None:
    report_path = task_dir / SPEC_VALIDATION_REPORT
    try:
        report = read_json_file(report_path)
    except (FileNotFoundError, OSError, UnicodeError, json.JSONDecodeError):
        return None
    if not isinstance(report, dict):
        return None
    if not _valid_report_shape(report):
        return None
    return report


def collect_spec_validation_gates(
    *,
    task: dict,
    task_dir: Path,
    action: str,
    refresh: bool = False,
    require_existing_report: bool = False,
    persist: bool = True,
) -> list[dict]:
    if not spec_validation_required(task, task_dir):
        return []

    report = load_spec_validation_report(task_dir)
    fingerprint = compute_source_fingerprint(task=task, task_dir=task_dir)
    stale = report is not None and report.get("source_fingerprint") != fingerprint

    if require_existing_report and report is None:
        _record_validation_state(task, None, status="missing", stale=False)
        return [
            make_gate_record(
                "SPEC_VALIDATION_MISSING",
                f"task spec must be validated before {action}",
                "spec_validation",
                created_at=utc_now(),
            )
        ]
    if require_existing_report and stale:
        _record_validation_state(task, report, status="stale", stale=True)
        return [
            make_gate_record(
                "SPEC_VALIDATION_STALE",
                f"task spec validation report is stale before {action}",
                "spec_validation",
                created_at=utc_now(),
            )
        ]

    if refresh or report is None or stale:
        report = build_spec_validation_report(task=task, task_dir=task_dir)
        if persist:
            write_json_file(task_dir / SPEC_VALIDATION_REPORT, report)
        _record_validation_state(task, report, stale=False)
    else:
        _record_validation_state(task, report, stale=False)
    return spec_validation_gates(report, action=action)


def spec_validation_required(task: dict, task_dir: Path | None = None) -> bool:
    meta = task.get("meta")
    if isinstance(meta, dict) and meta.get("spec_validation_required") is True:
        return True
    if isinstance(task.get("spec_validation"), dict):
        return True
    return bool(task_dir is not None and (task_dir / SPEC_VALIDATION_REPORT).exists())


def spec_validation_resource_payload(task: dict, task_dir: Path) -> dict[str, object]:
    report = load_spec_validation_report(task_dir)
    if report is None:
        return {
            "schema_version": SPEC_VALIDATION_SCHEMA_VERSION,
            "task_id": task.get("id"),
            "status": "not_recorded",
            "stale": False,
            "report_path": SPEC_VALIDATION_REPORT,
        }
    payload = dict(report)
    payload["stale"] = report.get("source_fingerprint") != compute_source_fingerprint(
        task=task,
        task_dir=task_dir,
    )
    payload["report_path"] = SPEC_VALIDATION_REPORT
    return payload


def spec_validation_gates(report: dict[str, object], *, action: str) -> list[dict]:
    raw_findings = report.get("findings")
    findings = [
        finding
        for finding in raw_findings if isinstance(finding, dict) and finding.get("severity") == "error"
    ] if isinstance(raw_findings, list) else []
    if not findings:
        return []
    preview = "; ".join(
        f"{finding.get('code')}: {finding.get('message')}"
        for finding in findings[:3]
    )
    if len(findings) > 3:
        preview += f"; +{len(findings) - 3} more"
    return [
        make_gate_record(
            "SPEC_VALIDATION_FAILED",
            f"task spec validation failed before {action}: {preview}",
            "spec_validation",
            created_at=utc_now(),
        )
    ]


def compute_source_fingerprint(*, task: dict, task_dir: Path) -> str:
    payload: list[dict[str, object]] = [
        {"key": "schema_version", "value": SPEC_VALIDATION_SCHEMA_VERSION},
        {"key": "task_id", "value": task.get("id")},
    ]
    for key in _required_doc_keys(task):
        relative_path = str(task.get("docs", {}).get(key) or "")
        doc_path = _safe_doc_path(task_dir, relative_path)
        digest = None
        if doc_path is not None and doc_path.is_file():
            digest = hashlib.sha256(doc_path.read_bytes()).hexdigest()
        payload.append({"key": key, "path": relative_path, "sha256": digest})
    meta = task.get("meta") if isinstance(task.get("meta"), dict) else {}
    payload.extend(
        [
            {"key": "type", "value": task.get("type")},
            {"key": "owned_paths", "value": meta.get("owned_paths", [])},
            {"key": "prerequisite_task_ids", "value": meta.get("prerequisite_task_ids", [])},
        ]
    )
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _record_validation_state(
    task: dict,
    report: dict[str, object] | None,
    *,
    status: str | None = None,
    stale: bool,
) -> None:
    summary = report.get("summary") if isinstance(report, dict) else {}
    if not isinstance(summary, dict):
        summary = {}
    task["spec_validation"] = {
        "status": status or (report.get("status") if isinstance(report, dict) else "missing"),
        "stale": stale,
        "checked_at": report.get("checked_at") if isinstance(report, dict) else None,
        "report_path": SPEC_VALIDATION_REPORT,
        "source_fingerprint": report.get("source_fingerprint") if isinstance(report, dict) else None,
        "error_count": summary.get("error_count", 0),
        "warning_count": summary.get("warning_count", 0),
    }


def _valid_report_shape(report: dict[str, object]) -> bool:
    if report.get("schema_version") != SPEC_VALIDATION_SCHEMA_VERSION:
        return False
    if not isinstance(report.get("task_id"), str):
        return False
    if report.get("status") not in {"passed", "warning", "failed"}:
        return False
    if not isinstance(report.get("checked_at"), str):
        return False
    if not isinstance(report.get("source_fingerprint"), str):
        return False

    summary = report.get("summary")
    if not isinstance(summary, dict):
        return False
    for key in ("error_count", "warning_count", "finding_count"):
        value = summary.get(key)
        if type(value) is not int or value < 0:
            return False

    gate_codes = report.get("gate_codes")
    if not isinstance(gate_codes, list) or not all(isinstance(code, str) for code in gate_codes):
        return False
    findings = report.get("findings")
    if not isinstance(findings, list):
        return False
    valid_findings = all(
        isinstance(finding, dict)
        and isinstance(finding.get("code"), str)
        and finding.get("severity") in {"error", "warning"}
        and isinstance(finding.get("source"), str)
        and isinstance(finding.get("message"), str)
        for finding in findings
    )
    if not valid_findings:
        return False

    error_count = sum(finding["severity"] == "error" for finding in findings)
    warning_count = sum(finding["severity"] == "warning" for finding in findings)
    expected_status = "failed" if error_count else "warning" if warning_count else "passed"
    expected_gate_codes = sorted(
        {str(finding["code"]) for finding in findings if finding["severity"] == "error"}
    )
    return (
        summary["error_count"] == error_count
        and summary["warning_count"] == warning_count
        and summary["finding_count"] == len(findings)
        and report["status"] == expected_status
        and gate_codes == expected_gate_codes
    )


def _load_docs(task: dict, task_dir: Path) -> dict[str, dict[str, object]]:
    docs: dict[str, dict[str, object]] = {}
    for key in _required_doc_keys(task):
        relative_path = str(task.get("docs", {}).get(key) or "")
        doc_path = _safe_doc_path(task_dir, relative_path)
        safe = bool(not relative_path or doc_path is not None)
        exists = bool(doc_path is not None and doc_path.is_file())
        content = doc_path.read_text(encoding="utf-8") if exists and doc_path is not None else ""
        docs[key] = {
            "relative_path": relative_path,
            "safe": safe,
            "exists": exists,
            "content": content,
            "sections": _sections(content),
        }
    return docs


def _required_doc_keys(task: dict) -> list[str]:
    if task.get("type") == "issue":
        return ["brief", "repro", "fix_plan"]
    return ["brief", "plan"]


def _validate_required_docs(task: dict, docs: dict[str, dict[str, object]]) -> list[dict[str, object]]:
    findings: list[dict[str, object]] = []
    for key in _required_doc_keys(task):
        doc = docs.get(key, {})
        relative_path = str(doc.get("relative_path") or "")
        if not relative_path:
            findings.append(_finding("REQUIRED_DOC_MISSING", "error", "docs", f"{key} document is missing from task metadata", key))
        elif not doc.get("safe"):
            findings.append(_finding("DOC_PATH_INVALID", "error", "docs", f"{relative_path} must stay inside the task directory", key))
        elif not doc.get("exists"):
            findings.append(_finding("REQUIRED_DOC_MISSING", "error", "docs", f"{relative_path} does not exist", key))
    return findings


def _validate_required_sections(task: dict, docs: dict[str, dict[str, object]]) -> list[dict[str, object]]:
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
    findings: list[dict[str, object]] = []
    for key, expected_sections in required.items():
        if key not in docs or not docs[key].get("exists"):
            continue
        sections = docs[key].get("sections")
        if not isinstance(sections, dict):
            sections = {}
        for section in expected_sections:
            if section not in sections:
                findings.append(_finding("REQUIRED_SECTION_MISSING", "error", "docs", f"{docs[key].get('relative_path')} must include `{section}`", key, section=section))
            elif not str(sections.get(section) or "").strip():
                findings.append(_finding("REQUIRED_SECTION_EMPTY", "error", "docs", f"{docs[key].get('relative_path')} section `{section}` is empty", key, section=section))
    return findings


def _validate_placeholders(docs: dict[str, dict[str, object]]) -> list[dict[str, object]]:
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
            findings.append(_finding("PLACEHOLDER_TEXT", "error", "docs", f"{doc.get('relative_path')} still contains generated placeholder text: {fragment}", key))
    return findings


def _validate_acceptance_criteria(task: dict, docs: dict[str, dict[str, object]]) -> list[dict[str, object]]:
    if task.get("type") != "feature":
        return []
    sections = docs.get("brief", {}).get("sections")
    block = str(sections.get("acceptance criteria") or "") if isinstance(sections, dict) else ""
    items = [match.group("item").strip() for match in CHECKLIST_PATTERN.finditer(block)]
    if any(item and not _is_placeholder(item) for item in items):
        return []
    return [_finding("ACCEPTANCE_CRITERIA_MISSING", "error", "docs", "feature task requires at least one concrete acceptance criterion", "brief", section="acceptance criteria")]


def _validate_scope(task: dict, docs: dict[str, dict[str, object]]) -> list[dict[str, object]]:
    meta = task.get("meta") if isinstance(task.get("meta"), dict) else {}
    owned_paths = meta.get("owned_paths")
    if isinstance(owned_paths, list) and any(str(path).strip() for path in owned_paths):
        return []
    for doc in docs.values():
        sections = doc.get("sections")
        if isinstance(sections, dict) and any(str(sections.get(name) or "").strip() for name in ("scope", "out of scope")):
            return []
    return [_finding("SCOPE_UNCLEAR", "warning", "task", "task has no owned paths or explicit scope section", None, remediation="Set owned_paths or add a concrete Scope section.")]


def _validate_test_strategy(task: dict, docs: dict[str, dict[str, object]]) -> list[dict[str, object]]:
    strategy = task.get("test_strategy") if isinstance(task.get("test_strategy"), dict) else {}
    findings: list[dict[str, object]] = []
    coverage_keys = (("normal_cases", "normal cases"), ("edge_cases", "edge cases"), ("exception_cases", "exception cases"))
    if not _has_waiver(docs, "COVERAGE_REQUIRED"):
        for strategy_key, label in coverage_keys:
            if not strategy.get(strategy_key):
                findings.append(_finding("COVERAGE_REQUIRED", "error", "strategy", f"test strategy must define at least one {label} item", _plan_doc_key(task), section=label))

    methods = list(strategy.get("verification_methods") or [])
    if not methods:
        if not _has_waiver(docs, "VERIFICATION_MAPPING_REQUIRED"):
            findings.append(_finding("VERIFICATION_MAPPING_REQUIRED", "error", "strategy", "verification mapping must define at least one method", _plan_doc_key(task), section="verification mapping"))
        return findings

    mapped_targets = {_normalize_target(item.get("target")) for item in methods if isinstance(item, dict)}
    coverage_targets = {
        _normalize_target(item.get("name"))
        for key, _ in coverage_keys
        for item in strategy.get(key, [])
        if isinstance(item, dict)
    }
    missing_targets = sorted(target for target in coverage_targets if target and target not in mapped_targets)
    if missing_targets and not _has_waiver(docs, "VERIFICATION_MAPPING_REQUIRED"):
        findings.append(_finding("VERIFICATION_MAPPING_INCOMPLETE", "error", "strategy", f"verification mapping is missing coverage targets: {', '.join(missing_targets[:3])}", _plan_doc_key(task), section="verification mapping"))

    for method in methods:
        method_text = str(method.get("method") or "").strip() if isinstance(method, dict) else ""
        if not method_text or _is_placeholder(method_text):
            findings.append(_finding("VERIFICATION_METHOD_PLACEHOLDER", "error", "strategy", "verification mapping method must name a concrete command, test, artifact, or review trigger", _plan_doc_key(task), section="verification mapping"))
            break
    return findings


def _validate_design(task: dict) -> list[dict[str, object]]:
    ensure_task_design_defaults(task)
    design = task["design"]
    findings: list[dict[str, object]] = []
    if design.get("layer_impact") in {"layer-adding", "layer-reshaping"} and design.get("mode") == "none":
        findings.append(_finding("DESIGN_MODE_INSUFFICIENT", "error", "design", "layer-adding or layer-reshaping work cannot use design_mode=none", _plan_doc_key(task), section="design evaluation"))
    missing_artifacts = [artifact for artifact in design.get("required_artifacts", []) if not design.get("artifacts", {}).get(artifact)]
    if missing_artifacts:
        findings.append(_finding("DESIGN_ARTIFACT_REQUIRED", "error", "design", f"required design artifacts are missing: {', '.join(missing_artifacts)}", _plan_doc_key(task), section="design artifacts"))
    return findings


def _validate_external_llm(task: dict) -> list[dict[str, object]]:
    strategy = task.get("test_strategy") if isinstance(task.get("test_strategy"), dict) else {}
    external = strategy.get("external_llm") if isinstance(strategy.get("external_llm"), dict) else {}
    if not external.get("required"):
        return []
    missing = [key for key in ("provider", "purpose", "trigger") if not str(external.get(key) or "").strip()]
    if not missing:
        return []
    return [_finding("EXTERNAL_LLM_POLICY_MISSING", "error", "strategy", f"external LLM review policy is missing: {', '.join(missing)}", _plan_doc_key(task), section="external llm review")]


def _validate_dependency_ordering(task: dict, task_dir: Path) -> list[dict[str, object]]:
    meta = task.get("meta") if isinstance(task.get("meta"), dict) else {}
    prerequisites = meta.get("prerequisite_task_ids")
    if prerequisites in (None, []):
        return []
    if not isinstance(prerequisites, list):
        return [_finding("PREREQUISITE_FORMAT_INVALID", "warning", "task", "prerequisite_task_ids should be a list of task ids", None)]
    findings: list[dict[str, object]] = []
    for raw_task_id in prerequisites:
        prerequisite_id = str(raw_task_id).strip()
        if not TASK_ID_PATTERN.fullmatch(prerequisite_id):
            findings.append(_finding("PREREQUISITE_FORMAT_INVALID", "warning", "task", f"invalid prerequisite task id: {prerequisite_id or '<empty>'}", None))
            continue
        prerequisite_file = task_dir.parent / prerequisite_id / "task.json"
        try:
            prerequisite = read_json_file(prerequisite_file)
        except (FileNotFoundError, OSError, UnicodeError, json.JSONDecodeError):
            findings.append(_finding("PREREQUISITE_NOT_FOUND", "warning", "task", f"prerequisite task is not readable: {prerequisite_id}", None))
            continue
        if not isinstance(prerequisite, dict):
            findings.append(_finding("PREREQUISITE_NOT_FOUND", "warning", "task", f"prerequisite task record is invalid: {prerequisite_id}", None))
            continue
        promotion = prerequisite.get("promotion") if isinstance(prerequisite.get("promotion"), dict) else {}
        ready = (
            prerequisite.get("status") == "closed"
            or promotion.get("status") == "promotion_recorded"
            or (
                prerequisite.get("plan_status") == "approved"
                and prerequisite.get("spec_status") == "frozen"
            )
        )
        if not ready:
            findings.append(_finding("PREREQUISITE_NOT_READY", "warning", "task", f"prerequisite task is not approved and frozen or merged: {prerequisite_id}", None))
    return findings


def _sections(content: str) -> dict[str, str]:
    matches = list(SECTION_PATTERN.finditer(content))
    sections: dict[str, str] = {}
    for index, match in enumerate(matches):
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(content)
        sections[match.group("title").strip().lower()] = content[start:end].strip()
    return sections


def _safe_doc_path(task_dir: Path, relative_path: str) -> Path | None:
    if not relative_path:
        return None
    candidate = Path(relative_path)
    if candidate.is_absolute() or ".." in candidate.parts:
        return None
    resolved_task_dir = task_dir.resolve()
    resolved_candidate = (task_dir / candidate).resolve()
    try:
        resolved_candidate.relative_to(resolved_task_dir)
    except ValueError:
        return None
    return resolved_candidate


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
    return any(fragment == normalized for fragment in PLACEHOLDER_FRAGMENTS)


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
    "SPEC_VALIDATION_GATE_CODES",
    "SPEC_VALIDATION_REPORT",
    "SPEC_VALIDATION_SCHEMA_VERSION",
    "SPEC_VALIDATION_SOURCES",
    "SpecValidationOutcome",
    "build_spec_validation_report",
    "collect_spec_validation_gates",
    "compute_source_fingerprint",
    "load_spec_validation_report",
    "persist_spec_validation_report",
    "spec_validation_gates",
    "spec_validation_required",
    "spec_validation_resource_payload",
    "validate_task_spec",
]
