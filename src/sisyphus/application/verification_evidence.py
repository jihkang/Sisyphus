from __future__ import annotations

from collections.abc import Mapping, Sequence


EVIDENCE_GRAPH_SCHEMA_VERSION = "sisyphus.evidence_graph.v1"
DEFAULT_EVIDENCE_GRAPH_PATH = "artifacts/evidence/evidence-graph.json"

EVIDENCE_VERDICT_SUPPORTS = "supports"
EVIDENCE_VERDICT_PARTIAL = "partial"
EVIDENCE_VERDICT_UNSUPPORTED = "unsupported"
EVIDENCE_VERDICT_MISSING = "missing"

EVIDENCE_IMPORTANCE_HIGH = "high"
EVIDENCE_IMPORTANCE_MEDIUM = "medium"
EVIDENCE_IMPORTANCE_LOW = "low"


def build_verification_evidence_graph(
    task: Mapping[str, object],
    command_results: Sequence[Mapping[str, object]],
    *,
    generated_at: str,
    conformance_status: str,
    changeset_path: str | None = None,
    changeset_present: bool = False,
) -> dict[str, object]:
    task_id = str(task.get("id") or "")
    verified = task.get("verify_status") == "passed"
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
            status=(
                EVIDENCE_VERDICT_SUPPORTS
                if conformance_status == "green"
                else EVIDENCE_VERDICT_PARTIAL
            ),
            importance=EVIDENCE_IMPORTANCE_MEDIUM,
            blocking=False,
        ),
    ]

    evidence = _command_evidence_items(task, command_results, generated_at)
    evidence.append(
        {
            "id": "ev-conformance-summary",
            "type": "conformance",
            "claim": "Task conformance is green.",
            "source": {"resource": f"task://{task_id}/conformance"},
            "verdict": (
                EVIDENCE_VERDICT_SUPPORTS
                if conformance_status == "green"
                else EVIDENCE_VERDICT_PARTIAL
            ),
            "importance": EVIDENCE_IMPORTANCE_MEDIUM,
            "reproducibility": "high",
            "observed_at": generated_at,
            "blocking": False,
            "linked_subtask": None,
            "linked_spec_section": None,
            "supports": ["claim-conformance-green"],
        }
    )
    if changeset_path and changeset_present:
        evidence.append(_changeset_evidence_item(changeset_path, generated_at))

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
        "generated_at": generated_at,
        "verify_status": task.get("verify_status"),
        "claims": claims,
        "curated_evidence": evidence,
        "unsupported_claims": unsupported_claims,
        "blocking_gaps": blocking_gaps,
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
                "verdict": (
                    EVIDENCE_VERDICT_SUPPORTS
                    if task.get("verify_status") == "passed"
                    else EVIDENCE_VERDICT_UNSUPPORTED
                ),
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
        passed = str(result.get("status") or "") == "passed"
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


def _changeset_evidence_item(relative_path: str, observed_at: str) -> dict[str, object]:
    return {
        "id": "ev-changeset",
        "type": "changeset",
        "claim": "Task changeset is present.",
        "source": {"path": relative_path},
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


__all__ = [
    "DEFAULT_EVIDENCE_GRAPH_PATH",
    "EVIDENCE_GRAPH_SCHEMA_VERSION",
    "EVIDENCE_IMPORTANCE_HIGH",
    "EVIDENCE_IMPORTANCE_LOW",
    "EVIDENCE_IMPORTANCE_MEDIUM",
    "EVIDENCE_VERDICT_MISSING",
    "EVIDENCE_VERDICT_PARTIAL",
    "EVIDENCE_VERDICT_SUPPORTS",
    "EVIDENCE_VERDICT_UNSUPPORTED",
    "build_verification_evidence_graph",
]
