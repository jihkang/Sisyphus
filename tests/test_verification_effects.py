from __future__ import annotations

import json
from pathlib import Path
import shlex
import sys
import tempfile
import time
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from sisyphus.application.verification_records import command_execution_to_record
from sisyphus.domain.verification import CommandExecution, VerificationStatus
from sisyphus.evidence_graph import build_evidence_graph
from sisyphus.infra.config.loader import load_config
from sisyphus.infra.verification.adapters import (
    ConformanceVerificationAdapter,
    EvidenceGraphAdapter,
    RepositoryVerificationEvidenceAdapter,
    ShellVerificationCommandAdapter,
)
from sisyphus.infra.verification.shell import (
    BoundedShellCommandRunner,
    parse_verification_command,
)


class FixedClock:
    def now(self) -> str:
        return "2026-07-19T12:00:00Z"


class VerificationEffectTests(unittest.TestCase):
    def test_shell_runner_bounds_output_and_retains_the_tail(self) -> None:
        script = "import sys; sys.stdout.write('x' * 10000 + 'TAIL\\n')"
        command = f"{shlex.quote(sys.executable)} -c {shlex.quote(script)}"

        receipt = BoundedShellCommandRunner(
            timeout_seconds=5.0,
            max_output_bytes=256,
        ).run(command, cwd=PROJECT_ROOT)

        self.assertEqual(receipt.exit_code, 0)
        self.assertFalse(receipt.timed_out)
        self.assertGreater(receipt.truncated_bytes, 0)
        self.assertLessEqual(len(receipt.output_tail.encode("utf-8")), 256)
        self.assertTrue(receipt.output_tail.endswith("TAIL\n"))

    def test_shell_runner_kills_a_timed_out_process_group(self) -> None:
        script = "import time; time.sleep(5)"
        command = f"{shlex.quote(sys.executable)} -c {shlex.quote(script)}"
        started = time.monotonic()

        receipt = BoundedShellCommandRunner(
            timeout_seconds=0.05,
            max_output_bytes=256,
        ).run(command, cwd=PROJECT_ROOT)

        self.assertTrue(receipt.timed_out)
        self.assertEqual(receipt.exit_code, 124)
        self.assertIn("timed out", receipt.error or "")
        self.assertLess(time.monotonic() - started, 2.0)

    def test_shell_runner_waits_when_the_command_closes_output_early(self) -> None:
        script = "import os, time; os.close(1); os.close(2); time.sleep(0.1)"
        command = f"{shlex.quote(sys.executable)} -c {shlex.quote(script)}"

        receipt = BoundedShellCommandRunner(
            timeout_seconds=2.0,
            max_output_bytes=256,
        ).run(command, cwd=PROJECT_ROOT)

        self.assertEqual(receipt.exit_code, 0)
        self.assertFalse(receipt.timed_out)
        self.assertGreaterEqual(receipt.duration_ms, 50)

    def test_verification_command_parser_rejects_multiline_and_nul_input(self) -> None:
        self.assertEqual(parse_verification_command("  echo ok  "), "echo ok")
        for command in ("echo one\necho two", "echo \x00 bad", "   "):
            with self.subTest(command=repr(command)):
                with self.assertRaises(ValueError):
                    parse_verification_command(command)

    def test_command_adapter_maps_timeout_to_a_bounded_failed_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            task_dir = root / ".planning" / "tasks" / "TF-1"
            task_dir.mkdir(parents=True)
            script = "import time; time.sleep(5)"
            command = f"{shlex.quote(sys.executable)} -c {shlex.quote(script)}"
            adapter = ShellVerificationCommandAdapter(
                root,
                load_config(root),
                FixedClock(),
                timeout_seconds=0.05,
                max_output_bytes=256,
            )

            result = adapter.run("TF-1", (command,))[0]

        self.assertEqual(result.status, VerificationStatus.FAILED)
        self.assertEqual(result.exit_code, 124)
        self.assertIn("timed out", result.output_excerpt)
        self.assertIsNotNone(result.duration_ms)

    def test_repository_evidence_adapter_matches_the_legacy_graph_contract(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            task_dir = root / ".planning" / "tasks" / "TF-1"
            task_dir.mkdir(parents=True)
            (task_dir / "CHANGESET.md").write_text("# Changeset\n", encoding="utf-8")
            task = _verified_task()
            execution = CommandExecution(
                name="echo ok",
                command="echo ok",
                status=VerificationStatus.PASSED,
                exit_code=0,
                started_at=FixedClock().now(),
                finished_at=FixedClock().now(),
                duration_ms=1,
                output_excerpt="ok",
            )
            adapter = RepositoryVerificationEvidenceAdapter(
                root,
                load_config(root),
                FixedClock(),
            )

            adapter.write("TF-1", task, (execution,))

            actual = json.loads(
                (task_dir / "artifacts" / "evidence" / "evidence-graph.json").read_text(
                    encoding="utf-8"
                )
            )
            expected = build_evidence_graph(
                task,
                task_dir,
                [command_execution_to_record(execution)],
                generated_at=FixedClock().now(),
            )

        self.assertEqual(actual, expected)
        self.assertIs(EvidenceGraphAdapter, RepositoryVerificationEvidenceAdapter)

    def test_conformance_adapter_injects_the_canonical_clock(self) -> None:
        task = _verified_task()

        ConformanceVerificationAdapter(FixedClock()).append(
            task,
            checkpoint_type="design_assessment",
            status="yellow",
            summary="review needed",
            source="verify",
            resolved=False,
            drift=0,
        )

        entry = task["conformance"]["history"][-1]
        self.assertEqual(entry["timestamp"], FixedClock().now())
        self.assertEqual(task["conformance"]["status"], "yellow")


def _verified_task() -> dict[str, object]:
    return {
        "id": "TF-1",
        "type": "feature",
        "status": "verified",
        "workflow_phase": "verified",
        "plan_status": "approved",
        "spec_status": "frozen",
        "verify_status": "passed",
        "docs": {"changeset": "CHANGESET.md"},
        "conformance": {"status": "green", "history": []},
        "subtasks": [],
    }


if __name__ == "__main__":
    unittest.main()
