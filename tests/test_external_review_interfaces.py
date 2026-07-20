from __future__ import annotations

import os
from pathlib import Path
from types import SimpleNamespace
import sys
import unittest
from unittest import mock


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))


from sisyphus.application.action_space import (  # noqa: E402
    ACTION_REGISTRY,
    ActionRiskLevel,
)
from sisyphus.interfaces.cli.dispatch import COMMAND_SPECS  # noqa: E402
from sisyphus.interfaces.cli.parser import build_parser  # noqa: E402
from sisyphus.interfaces.mcp.operator_auth import OPERATOR_CAPABILITY_ENV  # noqa: E402
from sisyphus.interfaces.mcp.registry import registered_tool_names  # noqa: E402
from sisyphus.interfaces.mcp.service import _trace_arguments  # noqa: E402
from sisyphus.interfaces.mcp.tools import mcp_tool_definitions  # noqa: E402
from sisyphus.interfaces.mcp.workflow_tools import call_workflow_tool  # noqa: E402


HEAD_SHA = "a" * 40
ENVELOPE_PATH = ".planning/tasks/TF-1/artifacts/reviews/review.json"


class ExternalReviewInterfaceTests(unittest.TestCase):
    def test_cli_parser_and_dispatch_expose_scope_and_envelope_recording(self) -> None:
        scope_args = build_parser().parse_args(["review", "scope", "TF-1", "--json"])
        record_args = build_parser().parse_args(
            ["review", "record", "TF-1", "--envelope", ENVELOPE_PATH, "--json"]
        )

        self.assertEqual(scope_args.review_command, "scope")
        self.assertTrue(scope_args.json)
        self.assertEqual(record_args.review_command, "record")
        self.assertEqual(record_args.envelope_path, ENVELOPE_PATH)
        definitions = {spec.path: spec for spec in COMMAND_SPECS}
        self.assertEqual(definitions[("review", "scope")].handler_name, "handle_review_scope")
        self.assertEqual(definitions[("review", "record")].handler_name, "handle_review_record")

    def test_mcp_record_requires_operator_capability_and_redacts_it_from_trace(self) -> None:
        tool_name = "sisyphus.record_external_review"
        definitions = {item["name"]: item for item in mcp_tool_definitions()}

        self.assertIn(tool_name, registered_tool_names())
        self.assertEqual(
            definitions[tool_name]["inputSchema"]["required"],
            ["task_id", "envelope_path", "operator_capability"],
        )
        self.assertTrue(
            definitions[tool_name]["inputSchema"]["properties"]["operator_capability"]["writeOnly"]
        )
        spec = ACTION_REGISTRY[tool_name]
        self.assertEqual(spec.risk, ActionRiskLevel.HUMAN_ONLY)
        self.assertTrue(spec.requires_human)

        captured: dict[str, object] = {}

        def record_review(**kwargs):
            captured.update(kwargs)
            return _result()

        args = {
            "task_id": "TF-1",
            "envelope_path": ENVELOPE_PATH,
            "operator_capability": "operator-secret",
        }
        with mock.patch.dict(
            os.environ,
            {OPERATOR_CAPABILITY_ENV: "operator-secret"},
            clear=False,
        ):
            payload = call_workflow_tool(
                repo_root=Path("/repo"),
                config=SimpleNamespace(),
                tool_name=tool_name,
                args=args,
                record_review=record_review,
            )

        self.assertEqual(payload["status"], "passed")
        self.assertEqual(captured["task_id"], "TF-1")
        self.assertEqual(captured["envelope_path"], ENVELOPE_PATH)
        self.assertNotIn("operator_capability", captured)
        self.assertEqual(
            _trace_arguments(tool_name, args)["operator_capability"],
            "<redacted>",
        )

    def test_mcp_record_rejects_unconfigured_or_invalid_operator_capability(self) -> None:
        args = {
            "task_id": "TF-1",
            "envelope_path": ENVELOPE_PATH,
            "operator_capability": "wrong",
        }
        with mock.patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(PermissionError, "not configured"):
                call_workflow_tool(
                    repo_root=Path("/repo"),
                    config=SimpleNamespace(),
                    tool_name="sisyphus.record_external_review",
                    args=args,
                    record_review=lambda **_: self.fail("record must not run"),
                )
        with mock.patch.dict(
            os.environ,
            {OPERATOR_CAPABILITY_ENV: "operator-secret"},
            clear=True,
        ):
            with self.assertRaisesRegex(PermissionError, "invalid"):
                call_workflow_tool(
                    repo_root=Path("/repo"),
                    config=SimpleNamespace(),
                    tool_name="sisyphus.record_external_review",
                    args=args,
                    record_review=lambda **_: self.fail("record must not run"),
                )


def _result() -> SimpleNamespace:
    return SimpleNamespace(
        task_id="TF-1",
        status="passed",
        provider="independent Codex reviewer",
        reviewer="independent-codex-agent",
        reviewed_head_sha=HEAD_SHA,
        scope_digest="sha256:" + "s" * 64,
        envelope_path=ENVELOPE_PATH,
        envelope_digest="sha256:" + "e" * 64,
        report_path=".planning/tasks/TF-1/artifacts/reviews/review.md",
        report_digest="sha256:" + "b" * 64,
        finding_count=0,
        blocking_finding_count=0,
        completed_at="2026-07-20T12:00:00Z",
    )


if __name__ == "__main__":
    unittest.main()
