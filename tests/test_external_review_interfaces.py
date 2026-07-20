from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
import sys
import unittest


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
from sisyphus.interfaces.mcp.registry import registered_tool_names  # noqa: E402
from sisyphus.interfaces.mcp.tools import mcp_tool_definitions  # noqa: E402
from sisyphus.interfaces.mcp.workflow_tools import call_workflow_tool  # noqa: E402


HEAD_SHA = "a" * 40


class ExternalReviewInterfaceTests(unittest.TestCase):
    def test_cli_parser_and_dispatch_expose_review_record(self) -> None:
        args = build_parser().parse_args(
            [
                "review",
                "record",
                "TF-1",
                "--reviewer",
                "independent-codex",
                "--verdict",
                "pass",
                "--report",
                "docs/reviews/external.md",
                "--head-sha",
                HEAD_SHA,
                "--finding-count",
                "2",
                "--json",
            ]
        )

        self.assertEqual(args.review_command, "record")
        self.assertEqual(args.reviewed_head_sha, HEAD_SHA)
        self.assertEqual(args.finding_count, 2)
        matching = [spec for spec in COMMAND_SPECS if spec.path == ("review", "record")]
        self.assertEqual(len(matching), 1)
        self.assertEqual(matching[0].handler_name, "handle_review_record")

    def test_mcp_registry_schema_and_executor_are_kept_in_sync(self) -> None:
        tool_name = "sisyphus.record_external_review"
        definitions = {item["name"]: item for item in mcp_tool_definitions()}

        self.assertIn(tool_name, registered_tool_names())
        self.assertIn(tool_name, definitions)
        self.assertEqual(
            definitions[tool_name]["inputSchema"]["required"],
            ["task_id", "reviewer", "verdict", "report_path", "reviewed_head_sha"],
        )
        spec = ACTION_REGISTRY[tool_name]
        self.assertEqual(spec.risk, ActionRiskLevel.HUMAN_ONLY)
        self.assertTrue(spec.requires_human)

        captured: dict[str, object] = {}

        def record_review(**kwargs):
            captured.update(kwargs)
            return SimpleNamespace(
                task_id="TF-1",
                status="passed",
                provider="independent Codex reviewer",
                reviewer="independent-codex",
                reviewed_head_sha=HEAD_SHA,
                report_path="docs/reviews/external.md",
                report_digest="sha256:" + "b" * 64,
                finding_count=0,
                blocking_finding_count=0,
                completed_at="2026-07-20T12:00:00Z",
            )

        payload = call_workflow_tool(
            repo_root=Path("/repo"),
            config=SimpleNamespace(),
            tool_name=tool_name,
            args={
                "task_id": "TF-1",
                "reviewer": "independent-codex",
                "verdict": "pass",
                "report_path": "docs/reviews/external.md",
                "reviewed_head_sha": HEAD_SHA,
            },
            record_review=record_review,
        )

        self.assertEqual(payload["status"], "passed")
        self.assertEqual(captured["task_id"], "TF-1")
        self.assertEqual(captured["blocking_finding_count"], 0)


if __name__ == "__main__":
    unittest.main()
