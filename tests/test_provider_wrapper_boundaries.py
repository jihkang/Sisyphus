from __future__ import annotations

from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from sisyphus.infra.providers.launch import ProviderLaunch as CanonicalProviderLaunch
from sisyphus.infra.providers.receipts import finalize_default_launch
from sisyphus.interfaces.provider_wrapper import (
    ConversationLaunchRequest,
    TaskLaunchRequest,
    parse_provider_wrapper_request,
)
from sisyphus.provider_wrapper import ProviderLaunch as PublicProviderLaunch


class ProviderWrapperBoundaryTests(unittest.TestCase):
    def test_implicit_task_request_preserves_options_and_command(self) -> None:
        request = parse_provider_wrapper_request(
            "codex",
            [
                "TF-1",
                "worker-1",
                "--role",
                "reviewer",
                "--owned-path",
                "src",
                "--provider-arg=--model",
                "--",
                "python",
                "-m",
                "unittest",
            ],
        )

        self.assertIsInstance(request, TaskLaunchRequest)
        self.assertEqual(request.task_id, "TF-1")
        self.assertEqual(request.role, "reviewer")
        self.assertEqual(request.owned_paths, ("src",))
        self.assertEqual(request.provider_args, ("--model",))
        self.assertEqual(request.command, ("python", "-m", "unittest"))

    def test_conversation_request_preserves_defaults(self) -> None:
        request = parse_provider_wrapper_request(
            "codex",
            ["conversation", "create a task", "--title", "Task title"],
        )

        self.assertIsInstance(request, ConversationLaunchRequest)
        self.assertEqual(request.message, "create a task")
        self.assertEqual(request.title, "Task title")
        self.assertEqual(request.task_type, "feature")
        self.assertEqual(request.agent_id, "worker-1")

    def test_public_launch_type_preserves_canonical_identity(self) -> None:
        self.assertIs(PublicProviderLaunch, CanonicalProviderLaunch)

    def test_finalizer_cleans_temp_file_and_records_blocked_status(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            output = root / "last-message.txt"
            output.write_text("STATUS: blocked\nworkspace unavailable\n", encoding="utf-8")
            mark_failed = mock.Mock()

            result = finalize_default_launch(
                repo_root=root,
                config=object(),
                task_id="TF-1",
                agent_id="worker-1",
                provider="codex",
                exit_code=0,
                output_last_message_path=output,
                mark_agent_failed=mark_failed,
            )

            self.assertEqual(result, 1)
            self.assertFalse(output.exists())
            mark_failed.assert_called_once()
            self.assertEqual(mark_failed.call_args.kwargs["error"], "agent reported blocked")


if __name__ == "__main__":
    unittest.main()
