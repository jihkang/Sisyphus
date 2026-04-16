from __future__ import annotations

import json
import shutil
from pathlib import Path
import sys
import tempfile
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from sisyphus.audit import run_verify
from sisyphus.closeout import run_close
from sisyphus.config import load_config


FIXTURES_ROOT = PROJECT_ROOT / "tests" / "fixtures"


class SisyphusGoldenTests(unittest.TestCase):
    maxDiff = None

    def _run_verify_fixture(self, fixture_name: str) -> tuple[dict, str, int]:
        fixture_root = FIXTURES_ROOT / fixture_name
        with tempfile.TemporaryDirectory() as tempdir:
            repo_root = Path(tempdir) / "repo"
            shutil.copytree(fixture_root / "input", repo_root)
            config = load_config(repo_root)
            task_file = next((repo_root / ".planning" / "tasks").glob("*/task.json"))
            task = json.loads(task_file.read_text(encoding="utf-8"))

            try:
                outcome = run_verify(repo_root, config, task["id"])
                exit_code = 0 if not outcome.gates else 1
            except Exception:
                exit_code = 2
                raise

            actual_task = json.loads(task_file.read_text(encoding="utf-8"))
            actual_verify = (task_file.parent / "VERIFY.md").read_text(encoding="utf-8")
            return actual_task, actual_verify, exit_code

    def test_feature_spec_incomplete_fixture(self) -> None:
        actual_task, actual_verify, exit_code = self._run_verify_fixture("feature_spec_incomplete")
        self._assert_fixture_matches("feature_spec_incomplete", actual_task, actual_verify, exit_code)

    def test_feature_spec_complete_fixture(self) -> None:
        actual_task, actual_verify, exit_code = self._run_verify_fixture("feature_spec_complete")
        self._assert_fixture_matches("feature_spec_complete", actual_task, actual_verify, exit_code)

    def test_issue_spec_incomplete_fixture(self) -> None:
        actual_task, actual_verify, exit_code = self._run_verify_fixture("issue_spec_incomplete")
        self._assert_fixture_matches("issue_spec_incomplete", actual_task, actual_verify, exit_code)

    def test_issue_spec_complete_fixture(self) -> None:
        actual_task, actual_verify, exit_code = self._run_verify_fixture("issue_spec_complete")
        self._assert_fixture_matches("issue_spec_complete", actual_task, actual_verify, exit_code)

    def test_close_requires_verify_fixture(self) -> None:
        actual_task, exit_code = self._run_close_fixture("close_requires_verify", git_init=False)
        self._assert_close_fixture_matches("close_requires_verify", actual_task, exit_code)

    def test_close_allows_verified_task_fixture(self) -> None:
        actual_task, exit_code = self._run_close_fixture("close_allows_verified_task", git_init=True)
        self._assert_close_fixture_matches("close_allows_verified_task", actual_task, exit_code)

    def _assert_fixture_matches(self, fixture_name: str, actual_task: dict, actual_verify: str, exit_code: int) -> None:
        expected_root = FIXTURES_ROOT / fixture_name / "expected"
        expected_task = json.loads((expected_root / "task.json").read_text(encoding="utf-8"))
        expected_verify = (expected_root / "VERIFY.md").read_text(encoding="utf-8")
        expected_result = json.loads((expected_root / "result.json").read_text(encoding="utf-8"))

        self.assertEqual(self._normalize_task(actual_task), expected_task)
        self.assertEqual(self._normalize_verify(actual_verify), expected_verify)
        self.assertEqual(exit_code, expected_result["exit_code"])
        self.assertEqual(actual_task["status"], expected_result["status"])
        self.assertEqual(actual_task["stage"], expected_result["stage"])

    def _run_close_fixture(self, fixture_name: str, git_init: bool) -> tuple[dict, int]:
        fixture_root = FIXTURES_ROOT / fixture_name
        with tempfile.TemporaryDirectory() as tempdir:
            repo_root = Path(tempdir) / "repo"
            shutil.copytree(fixture_root / "input", repo_root)
            if git_init:
                import subprocess

                subprocess.run(["git", "init"], cwd=repo_root, check=True, capture_output=True, text=True)
                subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo_root, check=True, capture_output=True, text=True)
                subprocess.run(["git", "config", "user.name", "Test User"], cwd=repo_root, check=True, capture_output=True, text=True)
                subprocess.run(["git", "add", "."], cwd=repo_root, check=True, capture_output=True, text=True)
                subprocess.run(["git", "commit", "-m", "fixture"], cwd=repo_root, check=True, capture_output=True, text=True)

            config = load_config(repo_root)
            task_file = next((repo_root / ".planning" / "tasks").glob("*/task.json"))
            task = json.loads(task_file.read_text(encoding="utf-8"))
            outcome = run_close(repo_root, config, task["id"], allow_dirty=False)
            exit_code = 0 if outcome.closed else 1
            actual_task = json.loads(task_file.read_text(encoding="utf-8"))
            return actual_task, exit_code

    def _assert_close_fixture_matches(self, fixture_name: str, actual_task: dict, exit_code: int) -> None:
        expected_root = FIXTURES_ROOT / fixture_name / "expected"
        expected_task = json.loads((expected_root / "task.json").read_text(encoding="utf-8"))
        expected_result = json.loads((expected_root / "result.json").read_text(encoding="utf-8"))

        self.assertEqual(self._normalize_close_task(actual_task), expected_task)
        self.assertEqual(exit_code, expected_result["exit_code"])
        self.assertEqual(actual_task["status"], expected_result["status"])
        self.assertEqual(actual_task["stage"], expected_result["stage"])

    def _normalize_task(self, task: dict) -> dict:
        return {
            "type": task["type"],
            "slug": task["slug"],
            "status": task["status"],
            "stage": task["stage"],
            "verify_status": task["verify_status"],
            "test_strategy": task["test_strategy"],
            "gates": [
                {
                    "code": gate["code"],
                    "message": gate["message"],
                }
                for gate in task["gates"]
            ],
        }

    def _normalize_close_task(self, task: dict) -> dict:
        return {
            "type": task["type"],
            "slug": task["slug"],
            "status": task["status"],
            "stage": task["stage"],
            "verify_status": task["verify_status"],
            "gates": [
                {
                    "code": gate["code"],
                    "message": gate["message"],
                }
                for gate in task["gates"]
            ],
            "meta": {
                "close_override_used": task["meta"]["close_override_used"],
            },
        }

    def _normalize_verify(self, content: str) -> str:
        lines = []
        for line in content.splitlines():
            if line.startswith("- Attempt: `"):
                lines.append("- Attempt: `<normalized>`")
            else:
                lines.append(line)
        return "\n".join(lines).strip() + "\n"


if __name__ == "__main__":
    unittest.main()
