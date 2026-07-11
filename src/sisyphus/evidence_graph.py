from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path
import json

from .conformance import summarize_task_conformance
from .gates import make_gate
from .state import utc_now


EVIDENCE_GRAPH_SCHEMA_VERSION = "sisyphus.evidence_graph.v1"
DEFAULT_EVIDENCE_GRAPH_PATH = Path("artifacts") / "evidence" / "evidence-graph.json"

EVIDENCE_VERDICT_SUPPORTS = "supports"
EVIDENCE_VERDICT_PARTIAL = "partial"
EVIDENCE_VERDICT_UNSUPPORTED = "unsupported"
EVIDENCE_VERDICT_MISSING = "missing"

EVIDENCE_IMPORTANCE_HIGH = "high"
EVIDENCE_IMPORTANCE_MEDIUM = "medium"
EVIDENCE_IMPORTANCE_LOW = "low"


def evidence_graph_path(task_dir: Path) -> Path:
    return task_dir / DEFAULT_EVIDENCE_GRAPH_PATH


def read_evidence_graph(task_dir: Path) -> dict[str, object] | None:
    path = evidence_graph_path(task_dir)
    if not path.exists():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"evidence graph must be a JSON object: {path}")
    return payload


def write_evidence_graph(task_dir: Path, graph: Mapping[str, object]) -> Path:
    path = evidence_graph_path(task_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(dict(graph), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def build_evidence_graph(
    task: Mapping[str, object],
    task_dir: Path,
    command_results: Sequence[Mapping[str, object]],
    *,
    generated_at: str | None = None,
) -> dict[str, object]:
    generated = generated_at or utc_now()
    task_id = str(task.get("id") or "")
    verified = task.get("verify_status") == "passed"
    conformance = summarize_task_conformance(dict(task))
    conformance_status = str(conformance.get("status") or "unknown")

    claims = [
        _claim(
            "claim-verify-passed",
            "Sisyphus verification passed.",
            status=EVIDENCE_VERDICT_SUPPORTS if verified else EVIDENCE_VERDICT_UNSUPPORTED,
            importance=EVIDENCE_IMPORTANCE_HIGH,
            blocking=True,
        ),
        _claim(
            "claim-conformance-green",
            "Task conformance is green.",
            status=EVIDENCE_VERDICT_SUPPORTS
            if conformance_status == "green"
            else EVIDENCE_VERDICT_PARTIAL,
            importance=EVIDENCE_IMPORTANCE_MEDIUM,
            blocking=False,
        ),
    ]

    evidence = _command_evidence_items(task, command_results, generated)
    evidence.append(
        {
            "id": "ev-conformance-summary",
            "type": "conformance",
            "claim": "Task conformance is green.",
            "source": {"resource": f"task://{task_id}/conformance"},
            "verdict": EVIDENCE_VERDICT_SUPPORTS
            if conformance_status == "green"
            else EVIDENCE_VERDICT_PARTIAL,
            "importance": EVIDENCE_IMPORTANCE_MEDIUM,
            "reproducibility": "high",
            "observed_at": generated,
            "blocking": False,
            "linked_subtask": None,
            "linked_spec_section": None,
            "supports": ["claim-conformance-green"],
        }
    )
    changeset_item = _changeset_evidence_item(task, task_dir, generated)
    if changeset_item is not None:
        evidence.append(changeset_item)

    unsupported_claims = [
        claim
        for claim in claims
        if claim.get("status") in {EVIDENCE_VERDICT_UNSUPPORTED, EVIDENCE_VERDICT_MISSING}
    ]
    blocking_gaps = [
        _blocking_gap_for_evidence(item)
        for item in evidence
        if _is_blocking_unsupported_evidence(item)
    ]

    return {
        "schema_version": EVIDENCE_GRAPH_SCHEMA_VERSION,
        "task_id": task_id,
        "generated_at": generated,
        "verify_status": task.get("verify_status"),
        "claims": claims,
        "curated_evidence": evidence,
        "unsupported_claims": unsupported_claims,
        "blocking_gaps": blocking_gaps,
    }


def summarize_evidence_graph(task: Mapping[str, object], task_dir: Path) -> dict[str, object]:
    try:
        graph = read_evidence_graph(task_dir)
    except (json.JSONDecodeError, ValueError) as exc:
        return {
            "status": "invalid",
            "path": str(DEFAULT_EVIDENCE_GRAPH_PATH),
            "error": str(exc),
            "curated_evidence": 0,
            "unsupported_claims": 0,
            "blocking_gaps": 0,
        }
    if graph is None:
        return {
            "status": "missing" if evidence_required_for_close(task) else "not_required",
            "path": str(DEFAULT_EVIDENCE_GRAPH_PATH),
            "curated_evidence": 0,
            "unsupported_claims": 0,
            "blocking_gaps": 0,
        }

    evidence = _list_field(graph, "curated_evidence")
    unsupported_claims = _list_field(graph, "unsupported_claims")
    blocking_gaps = _list_field(graph, "blocking_gaps")
    high_supported = sum(
        1
        for item in evidence
        if isinstance(item, Mapping)
        and item.get("importance") == EVIDENCE_IMPORTANCE_HIGH
        and item.get("verdict") == EVIDENCE_VERDICT_SUPPORTS
    )
    status = "complete"
    if blocking_gaps:
        status = "blocked"
    elif unsupported_claims:
        status = "partial"
    return {
        "status": status,
        "path": str(DEFAULT_EVIDENCE_GRAPH_PATH),
        "curated_evidence": len(evidence),
        "high_supported": high_supported,
        "unsupported_claims": len(unsupported_claims),
        "blocking_gaps": len(blocking_gaps),
    }


def collect_evidence_close_gates(task: Mapping[str, object], task_dir: Path) -> list[dict]:
    if not evidence_required_for_close(task):
        return []
    try:
        graph = read_evidence_graph(task_dir)
    except (json.JSONDecodeError, ValueError) as exc:
        return [
            make_gate(
                "EVIDENCE_GRAPH_INVALID",
                f"evidence graph is invalid: {exc}",
                source="evidence",
            )
        ]
    if graph is None:
        return [
            make_gate(
                "EVIDENCE_GRAPH_MISSING",
                "verified task is missing structured evidence graph",
                source="evidence",
            )
        ]

    gates: list[dict] = []
    evidence = _list_field(graph, "curated_evidence")
    unsupported_high = [
        item
        for item in evidence
        if isinstance(item, Mapping) and _is_blocking_unsupported_evidence(item)
    ]
    if unsupported_high:
        gates.append(
            make_gate(
                "EVIDENCE_UNSUPPORTED_HIGH_IMPORTANCE",
                "high-importance evidence contains unsupported or missing verdicts",
                source="evidence",
            )
        )

    blocking_gaps = _list_field(graph, "blocking_gaps")
    if blocking_gaps:
        gates.append(
            make_gate(
                "EVIDENCE_BLOCKING_GAP",
                "evidence graph contains blocking gaps",
                source="evidence",
            )
        )
    return gates


def evidence_required_for_close(task: Mapping[str, object]) -> bool:
    meta = task.get("meta", {})
    if not isinstance(meta, Mapping):
        return False
    return task.get("verify_status") == "passed" and bool(meta.get("evidence_graph_required"))


def evidence_resource_payload(task: Mapping[str, object], task_dir: Path) -> dict[str, object]:
    graph = read_evidence_graph(task_dir)
    if graph is not None:
        return graph
    return {
        "schema_version": EVIDENCE_GRAPH_SCHEMA_VERSION,
        "task_id": task.get("id"),
        "status": "missing" if evidence_required_for_close(task) else "not_required",
        "path": str(DEFAULT_EVIDENCE_GRAPH_PATH),
        "curated_evidence": [],
        "unsupported_claims": [],
        "blocking_gaps": [],
    }


def _claim(
    claim_id: str,
    text: str,
    *,
    status: str,
    importance: str,
    blocking: bool,
) -> dict[str, object]:
    return {
        "id": claim_id,
        "text": text,
        "status": status,
        "importance": importance,
        "blocking": blocking,
        "linked_spec_section": None,
        "linked_subtask": None,
    }


def _command_evidence_items(
    task: Mapping[str, object],
    command_results: Sequence[Mapping[str, object]],
    observed_at: str,
) -> list[dict[str, object]]:
    task_id = str(task.get("id") or "")
    if not command_results:
        return [
            {
                "id": "ev-verify-status",
                "type": "verification_status",
                "claim": "Sisyphus verification passed.",
                "source": {"resource": f"task://{task_id}/record"},
                "verdict": EVIDENCE_VERDICT_SUPPORTS
                if task.get("verify_status") == "passed"
                else EVIDENCE_VERDICT_UNSUPPORTED,
                "importance": EVIDENCE_IMPORTANCE_HIGH,
                "reproducibility": "medium",
                "observed_at": observed_at,
                "blocking": task.get("verify_status") != "passed",
                "linked_subtask": None,
                "linked_spec_section": None,
                "supports": ["claim-verify-passed"],
            }
        ]

    items: list[dict[str, object]] = []
    for index, result in enumerate(command_results, start=1):
        status = str(result.get("status") or "")
        passed = status == "passed"
        items.append(
            {
                "id": f"ev-command-{index:03d}",
                "type": "command_output",
                "claim": "Sisyphus verification command passed.",
                "source": {
                    "command": result.get("command"),
                    "exit_code": result.get("exit_code"),
                    "output_excerpt": result.get("output_excerpt"),
                },
                "verdict": EVIDENCE_VERDICT_SUPPORTS if passed else EVIDENCE_VERDICT_UNSUPPORTED,
                "importance": EVIDENCE_IMPORTANCE_HIGH,
                "reproducibility": "high",
                "observed_at": observed_at,
                "blocking": not passed,
                "linked_subtask": None,
                "linked_spec_section": None,
                "supports": ["claim-verify-passed"] if passed else [],
            }
        )
    return items


def _changeset_evidence_item(
    task: Mapping[str, object],
    task_dir: Path,
    observed_at: str,
) -> dict[str, object] | None:
    docs = task.get("docs", {})
    if not isinstance(docs, Mapping):
        return None
    relative = docs.get("changeset")
    if not relative:
        return None
    path = task_dir / str(relative)
    if not path.exists():
        return None
    return {
        "id": "ev-changeset",
        "type": "changeset",
        "claim": "Task changeset is present.",
        "source": {"path": str(relative)},
        "verdict": EVIDENCE_VERDICT_SUPPORTS,
        "importance": EVIDENCE_IMPORTANCE_LOW,
        "reproducibility": "medium",
        "observed_at": observed_at,
        "blocking": False,
        "linked_subtask": None,
        "linked_spec_section": None,
        "supports": [],
    }


def _is_blocking_unsupported_evidence(item: Mapping[str, object]) -> bool:
    return (
        item.get("importance") == EVIDENCE_IMPORTANCE_HIGH
        and item.get("verdict") in {EVIDENCE_VERDICT_UNSUPPORTED, EVIDENCE_VERDICT_MISSING}
        and bool(item.get("blocking", True))
    )


def _blocking_gap_for_evidence(item: Mapping[str, object]) -> dict[str, object]:
    return {
        "evidence_id": item.get("id"),
        "claim": item.get("claim"),
        "verdict": item.get("verdict"),
        "importance": item.get("importance"),
    }


def _list_field(graph: Mapping[str, object], key: str) -> list[object]:
    value = graph.get(key)
    return list(value) if isinstance(value, list) else []


__all__ = [
    "DEFAULT_EVIDENCE_GRAPH_PATH",
    "EVIDENCE_GRAPH_SCHEMA_VERSION",
    "build_evidence_graph",
    "collect_evidence_close_gates",
    "evidence_graph_path",
    "evidence_required_for_close",
    "evidence_resource_payload",
    "read_evidence_graph",
    "summarize_evidence_graph",
    "write_evidence_graph",
]
