from __future__ import annotations

import unittest

from sisyphus.application.verification_projection import (
    looks_like_unfilled_template,
    render_verify_markdown,
)
from sisyphus.domain.verification import CommandExecution, VerificationStatus


class VerificationProjectionTests(unittest.TestCase):
    def test_markdown_projection_preserves_verify_sections(self) -> None:
        command = CommandExecution(
            name="tests",
            command="python -m unittest",
            status=VerificationStatus.PASSED,
            exit_code=0,
            started_at="2026-07-20T00:00:00Z",
            finished_at="2026-07-20T00:00:01Z",
            duration_ms=1000,
            output_excerpt="ok",
        )

        markdown = render_verify_markdown(_task(), (command,))

        self.assertIn("# Verify", markdown)
        self.assertIn("## Spec Validation", markdown)
        self.assertIn("`python -m unittest` -> `passed`", markdown)
        self.assertIn("## Design Assessment", markdown)
        self.assertIn("## External LLM Review", markdown)

    def test_template_detection_keeps_existing_markers(self) -> None:
        self.assertTrue(looks_like_unfilled_template("Describe the problem"))
        self.assertTrue(looks_like_unfilled_template(""))
        self.assertFalse(looks_like_unfilled_template("Concrete implementation plan"))


def _task() -> dict:
    return {
        "id": "TF-1",
        "audit_attempts": 1,
        "max_audit_attempts": 10,
        "stage": "done",
        "verify_status": "passed",
        "gates": [],
        "test_strategy": {
            "normal_cases": [{"name": "normal"}],
            "edge_cases": [{"name": "edge"}],
            "exception_cases": [{"name": "exception"}],
            "verification_methods": [{"target": "normal", "method": "unit"}],
            "external_llm": {"required": False, "status": "not_needed"},
        },
        "spec_validation": {
            "status": "passed",
            "stale": False,
            "report_path": "artifacts/spec-validation/latest.json",
        },
        "design": {
            "mode": "full",
            "layer_impact": "layer-adding",
            "assessment": {
                "status": "appropriate",
                "replan_required": False,
                "missing_artifacts": [],
                "summary": "appropriate",
            },
        },
    }


if __name__ == "__main__":
    unittest.main()
