from __future__ import annotations

from copy import deepcopy
import unittest

from sisyphus.application.spec_validation_rules import (
    evaluate_spec_findings,
    parse_sections,
    prerequisite_task_ids_to_load,
    required_doc_keys,
)


class SpecValidationRuleTests(unittest.TestCase):
    def test_valid_preloaded_feature_spec_has_no_findings(self) -> None:
        task = _task()
        docs = _docs()
        parent_id = task["meta"]["prerequisite_task_ids"][0]

        findings = evaluate_spec_findings(
            task=task,
            docs=docs,
            prerequisites={
                parent_id: {
                    "plan_status": "approved",
                    "spec_status": "frozen",
                    "promotion": {},
                }
            },
        )

        self.assertEqual(findings, [])

    def test_missing_preloaded_prerequisite_is_a_policy_warning(self) -> None:
        findings = evaluate_spec_findings(
            task=_task(),
            docs=_docs(),
            prerequisites={},
        )

        self.assertEqual(
            [finding["code"] for finding in findings],
            ["PREREQUISITE_NOT_FOUND"],
        )
        self.assertEqual(findings[0]["severity"], "warning")

    def test_document_projection_helpers_are_deterministic(self) -> None:
        task = _task()

        self.assertEqual(required_doc_keys(task), ("brief", "plan"))
        self.assertEqual(
            prerequisite_task_ids_to_load(task),
            ("TF-20260701-feature-parent",),
        )
        self.assertEqual(
            parse_sections("# Title\n\n## One\nfirst\n\n## Two\nsecond\n"),
            {"one": "first", "two": "second"},
        )


def _task() -> dict:
    names = ("normal", "edge", "exception")
    return {
        "id": "TF-20260720-feature-child",
        "type": "feature",
        "docs": {"brief": "BRIEF.md", "plan": "PLAN.md"},
        "meta": {
            "owned_paths": ["src/sisyphus"],
            "prerequisite_task_ids": ["TF-20260701-feature-parent"],
        },
        "test_strategy": {
            "normal_cases": [{"name": names[0]}],
            "edge_cases": [{"name": names[1]}],
            "exception_cases": [{"name": names[2]}],
            "verification_methods": [
                {"target": name, "method": f"tests.test_rules::{name}"}
                for name in names
            ],
            "external_llm": {"required": False},
        },
        "design": {
            "mode": "full",
            "layer_impact": "layer-adding",
            "required_artifacts": [
                "connection_diagram",
                "sequence_diagram",
                "boundary_note",
            ],
            "artifacts": {
                "connection_diagram": "design/dependency.md",
                "sequence_diagram": "design/sequence.md",
                "boundary_note": "design/authority.md",
            },
        },
    }


def _docs() -> dict[str, dict[str, object]]:
    brief_sections = {
        "problem": "Mixed responsibilities",
        "desired outcome": "Clean boundaries",
        "acceptance criteria": "- [ ] Boundaries remain stable",
        "constraints": "Preserve behavior",
    }
    plan_sections = {
        "implementation plan": "Split policy from IO",
        "risks": "Schema drift",
        "design evaluation": "Full",
        "design artifacts": "Recorded",
        "test strategy": "Normal, edge, exception",
        "verification mapping": "Mapped",
        "external llm review": "Not required",
    }
    return {
        "brief": {
            "relative_path": "BRIEF.md",
            "safe": True,
            "exists": True,
            "content": "concrete brief",
            "sections": deepcopy(brief_sections),
        },
        "plan": {
            "relative_path": "PLAN.md",
            "safe": True,
            "exists": True,
            "content": "concrete plan",
            "sections": deepcopy(plan_sections),
        },
    }


if __name__ == "__main__":
    unittest.main()
