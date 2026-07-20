from __future__ import annotations

from pathlib import Path
import hashlib
import json

from ...application.contracts.spec_validation import (
    SPEC_VALIDATION_GATE_CODES,
    SPEC_VALIDATION_SOURCES,
)
from ...application.planning_records import dedupe_gate_records, make_gate_record
from ...application.results.planning import SpecValidationOutcome
from ...application.spec_validation_rules import (
    evaluate_spec_findings,
    parse_sections,
    prerequisite_task_ids_to_load,
    required_doc_keys,
)
from ...domain.task.design import ensure_task_design_defaults
from ...shared.clock import utc_now
from ..config.loader import SisyphusConfig
from ..documents.task_strategy import sync_test_strategy_from_docs
from ..persistence.json_store import read_json_file, write_json_file
from ..persistence.task_repository import load_task_record, save_task_record


SPEC_VALIDATION_REPORT = "artifacts/spec-validation/latest.json"
SPEC_VALIDATION_SCHEMA_VERSION = "sisyphus.spec_validation.v1"


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
    findings = evaluate_spec_findings(
        task=task,
        docs=docs,
        prerequisites=_load_prerequisite_records(task, task_dir),
    )

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
    for key in required_doc_keys(task):
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
    for key in required_doc_keys(task):
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
            "sections": parse_sections(content),
        }
    return docs


def _load_prerequisite_records(task: dict, task_dir: Path) -> dict[str, object]:
    records: dict[str, object] = {}
    for prerequisite_id in prerequisite_task_ids_to_load(task):
        prerequisite_file = task_dir.parent / prerequisite_id / "task.json"
        try:
            records[prerequisite_id] = read_json_file(prerequisite_file)
        except (FileNotFoundError, OSError, UnicodeError, json.JSONDecodeError):
            continue
    return records


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
