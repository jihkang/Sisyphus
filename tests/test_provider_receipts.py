from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from sisyphus.infra.providers.launch import build_local_launch
from sisyphus.infra.providers.local_config import (
    LocalProviderConfig as CanonicalLocalProviderConfig,
    parse_local_provider_args as canonical_parse_local_provider_args,
)
from sisyphus.infra.providers.receipt_schema import (
    InvalidLocalAgentReceipt,
    parse_local_agent_receipt,
    read_local_agent_receipt,
    sign_local_agent_receipt,
)
from sisyphus.infra.providers.receipts import finalize_default_launch, read_receipt
from sisyphus.providers.local_openai import (
    LocalProviderConfig as PublicLocalProviderConfig,
    parse_local_provider_args as public_parse_local_provider_args,
)


@dataclass
class PromptFixture:
    workdir: Path
    prompt: str = "bounded prompt\n"
    owned_paths: tuple[str, ...] = ("src",)
    observation_hash: str | None = "sha256:observation"


class ProviderReceiptTests(unittest.TestCase):
    def test_public_local_provider_config_preserves_canonical_identity(self) -> None:
        self.assertIs(PublicLocalProviderConfig, CanonicalLocalProviderConfig)
        self.assertIs(
            public_parse_local_provider_args,
            canonical_parse_local_provider_args,
        )

    def test_signed_receipt_parser_rejects_payload_tampering(self) -> None:
        receipt = sign_local_agent_receipt(_receipt(request_digest="sha256:" + "1" * 64))

        self.assertEqual(parse_local_agent_receipt(receipt), receipt)
        receipt["status"] = "failed"
        with self.assertRaisesRegex(InvalidLocalAgentReceipt, "digest"):
            parse_local_agent_receipt(receipt)

    def test_receipt_reader_rejects_a_symbolic_link(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            target = root / "target.json"
            target.write_text("{}", encoding="utf-8")
            link = root / "receipt.json"
            try:
                link.symlink_to(target)
            except OSError as exc:
                self.skipTest(f"symbolic links are unavailable: {exc}")

            with self.assertRaises(InvalidLocalAgentReceipt):
                read_local_agent_receipt(link)
            self.assertIsNone(read_receipt(link))

    def test_finalizer_rejects_a_receipt_bound_to_another_request(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            output = root / "last.txt"
            output.write_text("STATUS: completed\ndone\n", encoding="utf-8")
            receipt_path = root / "receipt.json"
            from sisyphus.infra.persistence.json_store import write_json_file

            write_json_file(
                receipt_path,
                sign_local_agent_receipt(_receipt(request_digest="sha256:" + "1" * 64)),
            )
            mark_failed = mock.Mock()

            result = finalize_default_launch(
                repo_root=root,
                config=object(),
                task_id="TF-1",
                agent_id="worker-1",
                provider="gemma",
                exit_code=0,
                output_last_message_path=output,
                receipt_path=receipt_path,
                workdir=root,
                expected_request_digest="sha256:" + "2" * 64,
                mark_agent_failed=mark_failed,
                persist_receipt=mock.Mock(),
            )

        self.assertEqual(result, 1)
        self.assertIn("request digest", mark_failed.call_args.kwargs["error"])

    def test_local_launch_emits_a_stable_request_digest(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)

            def prompt_builder(**_kwargs) -> PromptFixture:
                return PromptFixture(workdir=root)

            first = build_local_launch(
                provider="gemma",
                repo_root=root,
                config=object(),
                task_id="TF-1",
                extra_instruction=None,
                provider_args=["--no-fallback", "--test-command", "python -m unittest"],
                owned_paths=None,
                codex_prompt_builder=prompt_builder,
                local_prompt_builder=prompt_builder,
                provider_available=lambda _config: True,
            )
            second = build_local_launch(
                provider="gemma",
                repo_root=root,
                config=object(),
                task_id="TF-1",
                extra_instruction=None,
                provider_args=["--no-fallback", "--test-command", "python -m unittest"],
                owned_paths=None,
                codex_prompt_builder=prompt_builder,
                local_prompt_builder=prompt_builder,
                provider_available=lambda _config: True,
            )
            self.addCleanup(first.output_last_message_path.unlink, missing_ok=True)
            self.addCleanup(first.receipt_path.unlink, missing_ok=True)
            self.addCleanup(second.output_last_message_path.unlink, missing_ok=True)
            self.addCleanup(second.receipt_path.unlink, missing_ok=True)

        self.assertEqual(first.request_digest, second.request_digest)
        self.assertRegex(first.request_digest or "", r"^sha256:[0-9a-f]{64}$")
        digest_index = first.command.index("--request-digest") + 1
        self.assertEqual(first.command[digest_index], first.request_digest)


def _receipt(*, request_digest: str) -> dict[str, object]:
    return {
        "schema_version": "sisyphus.local_agent_run.v1",
        "status": "completed",
        "request_digest": request_digest,
        "completion_facts": {
            "completion_ready": True,
            "changed_files": ["src/app.py"],
            "baseline_test_step": 1,
            "last_mutation_step": 2,
            "last_successful_test_step": 3,
        },
        "events": [],
    }


if __name__ == "__main__":
    unittest.main()
