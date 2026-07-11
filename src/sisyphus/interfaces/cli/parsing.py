from __future__ import annotations

import json

from ...evolution.handoff import EvolutionEvidenceSummary, EvolutionVerificationObligation


def parse_changed_file_json(entries: list[str] | None) -> list[dict[str, object]] | None:
    if not entries:
        return None
    parsed: list[dict[str, object]] = []
    for entry in entries:
        value = json.loads(entry)
        if not isinstance(value, dict):
            raise ValueError("each --changed-file-json entry must decode to an object")
        parsed.append({str(key): value[key] for key in value})
    return parsed


def parse_verification_obligation_json(
    entries: list[str] | None,
) -> tuple[EvolutionVerificationObligation, ...] | None:
    if entries is None:
        return None
    obligations: list[EvolutionVerificationObligation] = []
    for index, entry in enumerate(entries, start=1):
        value = json.loads(entry)
        if not isinstance(value, dict):
            raise ValueError(f"verification obligation entry {index} must decode to an object")
        claim = str(value.get("claim", "")).strip()
        method = str(value.get("method", "")).strip()
        if not claim or not method:
            raise ValueError(
                f"verification obligation entry {index} requires non-empty `claim` and `method`"
            )
        obligations.append(
            EvolutionVerificationObligation(
                claim=claim,
                method=method,
                required=bool(value.get("required", True)),
            )
        )
    return tuple(obligations)


def parse_evidence_summary_json(
    entries: list[str] | None,
) -> tuple[EvolutionEvidenceSummary, ...] | None:
    if entries is None:
        return None
    evidence: list[EvolutionEvidenceSummary] = []
    for index, entry in enumerate(entries, start=1):
        value = json.loads(entry)
        if not isinstance(value, dict):
            raise ValueError(f"evidence summary entry {index} must decode to an object")
        kind = str(value.get("kind", "")).strip()
        summary = str(value.get("summary", "")).strip()
        if not kind or not summary:
            raise ValueError(
                f"evidence summary entry {index} requires non-empty `kind` and `summary`"
            )
        locator = value.get("locator")
        evidence.append(
            EvolutionEvidenceSummary(
                kind=kind,
                summary=summary,
                locator=str(locator).strip() if locator not in (None, "") else None,
            )
        )
    return tuple(evidence)


__all__ = [
    "parse_changed_file_json",
    "parse_evidence_summary_json",
    "parse_verification_obligation_json",
]
