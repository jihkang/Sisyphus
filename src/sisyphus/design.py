from __future__ import annotations

from pathlib import Path
import copy
import re


DESIGN_MODE_NONE = "none"
DESIGN_MODE_LIGHT = "light"
DESIGN_MODE_FULL = "full"
DESIGN_MODES = {
    DESIGN_MODE_NONE,
    DESIGN_MODE_LIGHT,
    DESIGN_MODE_FULL,
}

DESIGN_CONFIDENCE_LOW = "low"
DESIGN_CONFIDENCE_MEDIUM = "medium"
DESIGN_CONFIDENCE_HIGH = "high"
DESIGN_CONFIDENCE_LEVELS = {
    DESIGN_CONFIDENCE_LOW,
    DESIGN_CONFIDENCE_MEDIUM,
    DESIGN_CONFIDENCE_HIGH,
}

LAYER_IMPACT_PRESERVING = "layer-preserving"
LAYER_IMPACT_TOUCHING = "layer-touching"
LAYER_IMPACT_RESHAPING = "layer-reshaping"
LAYER_IMPACT_ADDING = "layer-adding"
LAYER_IMPACTS = {
    LAYER_IMPACT_PRESERVING,
    LAYER_IMPACT_TOUCHING,
    LAYER_IMPACT_RESHAPING,
    LAYER_IMPACT_ADDING,
}

DESIGN_ARTIFACT_CONNECTION_DIAGRAM = "connection_diagram"
DESIGN_ARTIFACT_SEQUENCE_DIAGRAM = "sequence_diagram"
DESIGN_ARTIFACT_BOUNDARY_NOTE = "boundary_note"
DESIGN_ARTIFACTS = (
    DESIGN_ARTIFACT_CONNECTION_DIAGRAM,
    DESIGN_ARTIFACT_SEQUENCE_DIAGRAM,
    DESIGN_ARTIFACT_BOUNDARY_NOTE,
)

DESIGN_ASSESSMENT_NOT_ASSESSED = "not_assessed"
DESIGN_ASSESSMENT_APPROPRIATE = "appropriate"
DESIGN_ASSESSMENT_UNDERDESIGNED = "underdesigned"
DESIGN_ASSESSMENT_OVERDESIGNED = "overdesigned"
DESIGN_ASSESSMENT_STATUSES = {
    DESIGN_ASSESSMENT_NOT_ASSESSED,
    DESIGN_ASSESSMENT_APPROPRIATE,
    DESIGN_ASSESSMENT_UNDERDESIGNED,
    DESIGN_ASSESSMENT_OVERDESIGNED,
}

SECTION_PATTERN = re.compile(r"^##\s+(?P<title>.+?)\s*$", re.MULTILINE)

PLACEHOLDER_VALUES = {
    "yes/no",
    "low/medium/high",
    "none | light | full",
    "layer-preserving | layer-touching | layer-reshaping | layer-adding",
    "none | connection_diagram, sequence_diagram, boundary_note",
    "existing contract only / crosses a few modules / introduces a new layer",
    "n/a",
    "none",
}

ARTIFACT_LABEL_MAP = {
    "connection diagram": DESIGN_ARTIFACT_CONNECTION_DIAGRAM,
    "sequence diagram": DESIGN_ARTIFACT_SEQUENCE_DIAGRAM,
    "boundary note": DESIGN_ARTIFACT_BOUNDARY_NOTE,
}


def default_task_design() -> dict:
    return {
        "mode": DESIGN_MODE_NONE,
        "decision_reason": None,
        "confidence": None,
        "layer_impact": LAYER_IMPACT_PRESERVING,
        "layer_decision_reason": None,
        "required_artifacts": [],
        "artifacts": {
            DESIGN_ARTIFACT_CONNECTION_DIAGRAM: None,
            DESIGN_ARTIFACT_SEQUENCE_DIAGRAM: None,
            DESIGN_ARTIFACT_BOUNDARY_NOTE: None,
        },
        "frozen": {
            "mode": DESIGN_MODE_NONE,
            "layer_impact": LAYER_IMPACT_PRESERVING,
            "required_artifacts": [],
            "artifacts": {
                DESIGN_ARTIFACT_CONNECTION_DIAGRAM: None,
                DESIGN_ARTIFACT_SEQUENCE_DIAGRAM: None,
                DESIGN_ARTIFACT_BOUNDARY_NOTE: None,
            },
            "anchor_summary": None,
            "frozen_at": None,
        },
        "assessment": {
            "status": DESIGN_ASSESSMENT_NOT_ASSESSED,
            "summary": None,
            "replan_required": False,
            "escalation_reason": None,
            "missing_artifacts": [],
        },
    }


def ensure_task_design_defaults(task: dict) -> dict:
    if not isinstance(task.get("design"), dict):
        task["design"] = default_task_design()
        return task

    design = task["design"]
    defaults = default_task_design()
    for key, value in defaults.items():
        if key not in design:
            design[key] = copy.deepcopy(value)

    design["mode"] = normalize_design_mode(design.get("mode"))
    design["confidence"] = normalize_design_confidence(design.get("confidence"))
    design["layer_impact"] = normalize_layer_impact(design.get("layer_impact"))
    design["decision_reason"] = _normalize_text_value(design.get("decision_reason"))
    design["layer_decision_reason"] = _normalize_text_value(design.get("layer_decision_reason"))
    design["required_artifacts"] = _normalize_artifact_names(design.get("required_artifacts"))

    if not isinstance(design.get("artifacts"), dict):
        design["artifacts"] = copy.deepcopy(defaults["artifacts"])
    for key in DESIGN_ARTIFACTS:
        design["artifacts"].setdefault(key, None)
        design["artifacts"][key] = _normalize_text_value(design["artifacts"].get(key))

    if not isinstance(design.get("frozen"), dict):
        design["frozen"] = copy.deepcopy(defaults["frozen"])
    frozen = design["frozen"]
    frozen["mode"] = normalize_design_mode(frozen.get("mode"))
    frozen["layer_impact"] = normalize_layer_impact(frozen.get("layer_impact"))
    frozen["required_artifacts"] = _normalize_artifact_names(frozen.get("required_artifacts"))
    frozen["anchor_summary"] = _normalize_text_value(frozen.get("anchor_summary"))
    if not isinstance(frozen.get("artifacts"), dict):
        frozen["artifacts"] = copy.deepcopy(defaults["frozen"]["artifacts"])
    for key in DESIGN_ARTIFACTS:
        frozen["artifacts"].setdefault(key, None)
        frozen["artifacts"][key] = _normalize_text_value(frozen["artifacts"].get(key))

    if not isinstance(design.get("assessment"), dict):
        design["assessment"] = copy.deepcopy(defaults["assessment"])
    assessment = design["assessment"]
    assessment["status"] = normalize_design_assessment_status(assessment.get("status"))
    assessment["summary"] = _normalize_text_value(assessment.get("summary"))
    assessment["replan_required"] = bool(assessment.get("replan_required"))
    assessment["escalation_reason"] = _normalize_text_value(assessment.get("escalation_reason"))
    assessment["missing_artifacts"] = _normalize_artifact_names(assessment.get("missing_artifacts"))
    return task


def normalize_design_mode(value: object | None) -> str:
    normalized = str(value or DESIGN_MODE_NONE).strip().lower()
    if normalized not in DESIGN_MODES:
        return DESIGN_MODE_NONE
    return normalized


def normalize_design_confidence(value: object | None) -> str | None:
    normalized = _normalize_text_value(value)
    if normalized is None:
        return None
    lowered = normalized.lower()
    if lowered not in DESIGN_CONFIDENCE_LEVELS:
        return None
    return lowered


def normalize_layer_impact(value: object | None) -> str:
    normalized = str(value or LAYER_IMPACT_PRESERVING).strip().lower()
    if normalized not in LAYER_IMPACTS:
        return LAYER_IMPACT_PRESERVING
    return normalized


def normalize_design_assessment_status(value: object | None) -> str:
    normalized = str(value or DESIGN_ASSESSMENT_NOT_ASSESSED).strip().lower()
    if normalized not in DESIGN_ASSESSMENT_STATUSES:
        return DESIGN_ASSESSMENT_NOT_ASSESSED
    return normalized


def sync_design_from_docs(task: dict, task_dir: Path, *, source_name: str) -> dict:
    ensure_task_design_defaults(task)
    source_path = task_dir / source_name
    if not source_path.exists():
        return task

    content = source_path.read_text(encoding="utf-8")
    design_eval = _extract_key_value_section(content, "Design Evaluation")
    design_artifacts = _extract_key_value_section(content, "Design Artifacts")

    design = task["design"]
    if design_eval:
        design["mode"] = normalize_design_mode(design_eval.get("design mode"))
        design["decision_reason"] = _normalize_text_value(design_eval.get("decision reason"))
        design["confidence"] = normalize_design_confidence(design_eval.get("confidence"))
        design["layer_impact"] = normalize_layer_impact(design_eval.get("layer impact"))
        design["layer_decision_reason"] = _normalize_text_value(design_eval.get("layer decision reason"))
        design["required_artifacts"] = _parse_artifact_list(design_eval.get("required design artifacts"))

    if design_artifacts:
        for label, artifact_name in ARTIFACT_LABEL_MAP.items():
            design["artifacts"][artifact_name] = _normalize_artifact_reference(design_artifacts.get(label))

    ensure_task_design_defaults(task)
    return task


def freeze_design_anchor(task: dict, *, frozen_at: str) -> dict:
    ensure_task_design_defaults(task)
    design = task["design"]
    design["frozen"] = {
        "mode": design["mode"],
        "layer_impact": design["layer_impact"],
        "required_artifacts": list(design["required_artifacts"]),
        "artifacts": {
            key: value
            for key, value in design["artifacts"].items()
        },
        "anchor_summary": summarize_design_anchor(design),
        "frozen_at": frozen_at,
    }
    design["assessment"]["status"] = DESIGN_ASSESSMENT_NOT_ASSESSED
    design["assessment"]["summary"] = None
    design["assessment"]["replan_required"] = False
    design["assessment"]["escalation_reason"] = None
    design["assessment"]["missing_artifacts"] = []
    return task


def evaluate_design_adequacy(task: dict) -> dict:
    ensure_task_design_defaults(task)
    design = task["design"]
    assessment = design["assessment"]
    missing_artifacts = [
        artifact
        for artifact in design["required_artifacts"]
        if not design["artifacts"].get(artifact)
    ]

    summary: str
    status: str
    replan_required = False
    escalation_reason = None

    if design["layer_impact"] in {LAYER_IMPACT_RESHAPING, LAYER_IMPACT_ADDING} and design["mode"] == DESIGN_MODE_NONE:
        status = DESIGN_ASSESSMENT_UNDERDESIGNED
        replan_required = True
        escalation_reason = "layer-changing work cannot stay in design_mode=none"
        summary = "layer-changing task was planned without an explicit design anchor"
    elif design["mode"] in {DESIGN_MODE_LIGHT, DESIGN_MODE_FULL} and design["required_artifacts"] and missing_artifacts:
        status = DESIGN_ASSESSMENT_UNDERDESIGNED
        replan_required = True
        escalation_reason = "required design artifacts are still missing from the plan"
        summary = "design artifacts required by the plan are missing from the recorded design bundle"
    elif design["mode"] == DESIGN_MODE_FULL and not design["required_artifacts"] and not any(design["artifacts"].values()):
        status = DESIGN_ASSESSMENT_UNDERDESIGNED
        replan_required = True
        escalation_reason = "full design mode has no recorded artifacts"
        summary = "full design mode was selected without any concrete design anchor"
    elif design["mode"] == DESIGN_MODE_FULL and design["layer_impact"] == LAYER_IMPACT_PRESERVING and any(design["artifacts"].values()):
        status = DESIGN_ASSESSMENT_OVERDESIGNED
        summary = "full design mode may be heavier than necessary for layer-preserving work"
    else:
        status = DESIGN_ASSESSMENT_APPROPRIATE
        summary = "design depth matches the current task shape"

    assessment["status"] = status
    assessment["summary"] = summary
    assessment["replan_required"] = replan_required
    assessment["escalation_reason"] = escalation_reason
    assessment["missing_artifacts"] = missing_artifacts
    ensure_task_design_defaults(task)
    return assessment


def summarize_design_anchor(design: dict) -> str:
    mode = normalize_design_mode(design.get("mode"))
    layer_impact = normalize_layer_impact(design.get("layer_impact"))
    required_artifacts = _normalize_artifact_names(design.get("required_artifacts"))
    artifact_count = sum(1 for value in dict(design.get("artifacts") or {}).values() if _normalize_text_value(value))
    parts = [
        f"mode={mode}",
        f"layer={layer_impact}",
    ]
    if required_artifacts:
        parts.append(f"required={','.join(required_artifacts)}")
    if artifact_count:
        parts.append(f"recorded={artifact_count}")
    return ", ".join(parts)


def _extract_key_value_section(content: str, title: str) -> dict[str, str]:
    block = _extract_section_block(content, title)
    values: dict[str, str] = {}
    for line in block.splitlines():
        stripped = line.strip()
        if not stripped.startswith("- "):
            continue
        payload = stripped[2:]
        if ":" not in payload:
            continue
        key, value = payload.split(":", 1)
        values[key.strip().lower()] = value.strip().strip("`")
    return values


def _extract_section_block(content: str, title: str) -> str:
    matches = list(SECTION_PATTERN.finditer(content))
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


def _parse_artifact_list(value: str | None) -> list[str]:
    if not value:
        return []
    normalized = value.strip().strip("`")
    if not normalized or normalized.lower() in PLACEHOLDER_VALUES:
        return []
    items = [item.strip().lower() for item in normalized.split(",")]
    return _normalize_artifact_names(items)


def _normalize_artifact_names(values: object | None) -> list[str]:
    if isinstance(values, str):
        values = [item.strip() for item in values.split(",")]
    elif not isinstance(values, list):
        values = list(values) if isinstance(values, tuple) else []
    normalized: list[str] = []
    for value in values:
        item = str(value).strip().lower()
        if item in {"", "none", "n/a"}:
            continue
        if item not in DESIGN_ARTIFACTS:
            continue
        if item in normalized:
            continue
        normalized.append(item)
    return normalized


def _normalize_artifact_reference(value: str | None) -> str | None:
    normalized = _normalize_text_value(value)
    if normalized is None:
        return None
    if normalized.lower() in {"none", "n/a"}:
        return None
    return normalized


def _normalize_text_value(value: object | None) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip().strip("`")
    if not normalized:
        return None
    if normalized.lower() in PLACEHOLDER_VALUES:
        return None
    return normalized
