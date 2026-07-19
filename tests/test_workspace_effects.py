from __future__ import annotations

from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from sisyphus.infra.workspace.effects import PatchExecution
from sisyphus.infra.workspace.errors import WorkspaceGitError
from sisyphus.infra.workspace.executor import WorkspaceExecutor
from sisyphus.infra.workspace.git import SubprocessWorkspaceGit
from sisyphus.infra.workspace.test_runner import SubprocessWorkspaceTests


class WorkspaceEffectTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)
        (self.root / "app.py").write_text("value = 1\n", encoding="utf-8")
        self._git("init", "-b", "main")
        self._git("config", "user.email", "test@example.com")
        self._git("config", "user.name", "Test User")
        self._git("add", ".")
        self._git("commit", "-m", "initial")

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def _git(self, *args: str) -> None:
        subprocess.run(
            ["git", *args],
            cwd=self.root,
            check=True,
            capture_output=True,
            text=True,
        )

    def test_git_adapter_owns_queries_and_patch_processes(self) -> None:
        adapter = SubprocessWorkspaceGit(self.root, timeout_seconds=10.0)
        (self.root / "new.txt").write_text("new\n", encoding="utf-8")
        patch = """diff --git a/app.py b/app.py
--- a/app.py
+++ b/app.py
@@ -1 +1 @@
-value = 1
+value = 2
"""

        applied = adapter.apply_patch(patch)

        self.assertTrue(applied.ok)
        self.assertEqual((self.root / "app.py").read_text(encoding="utf-8"), "value = 2\n")
        self.assertEqual(set(adapter.changed_files()), {"app.py", "new.txt"})
        self.assertEqual(set(adapter.repository_files()), {"app.py", "new.txt"})
        self.assertIn("app.py", adapter.status())
        self.assertIn("app.py", adapter.diff_stat())

    def test_invalid_patch_remains_an_execution_failure(self) -> None:
        executor = WorkspaceExecutor(
            self.root,
            test_commands=(f'{sys.executable} -c "pass"',),
        )
        executor.execute({"action": "run_test", "command_id": 0}, step=1)

        result = executor.execute(
            {
                "action": "apply_patch",
                "patch": """diff --git a/app.py b/app.py
--- a/app.py
+++ b/app.py
@@ -1 +1 @@
-missing = 1
+value = 2
""",
            },
            step=2,
        )

        self.assertFalse(result["ok"])
        self.assertFalse(result["blocked"])
        self.assertIn("patch does not apply", result["error"])

    def test_test_adapter_rewrites_python_and_reports_timeout(self) -> None:
        interpreter = SubprocessWorkspaceTests(
            self.root,
            commands=('python -c "import sys; print(sys.executable)"',),
            timeout_seconds=10.0,
        ).run(0)
        timed_out = SubprocessWorkspaceTests(
            self.root,
            commands=('python -c "import time; time.sleep(1)"',),
            timeout_seconds=0.05,
        ).run(0)

        self.assertTrue(interpreter.ok)
        self.assertEqual(interpreter.output.strip(), sys.executable)
        self.assertFalse(timed_out.ok)
        self.assertIsNone(timed_out.exit_code)
        self.assertIn("timed out", timed_out.error or "")

    def test_executor_bounds_an_injected_git_failure(self) -> None:
        class FailingGit:
            def changed_files(self) -> tuple[str, ...]:
                raise WorkspaceGitError("x" * 1000)

            def repository_files(self) -> tuple[str, ...]:
                return ()

            def status(self) -> str:
                return ""

            def diff_stat(self) -> str:
                return ""

            def apply_patch(self, patch: str) -> PatchExecution:
                return PatchExecution(ok=False, error="patch failure")

        executor = WorkspaceExecutor(
            self.root,
            git_effects=FailingGit(),
            max_output_chars=256,
        )

        result = executor.execute({"action": "git_diff"}, step=1)

        self.assertFalse(result["ok"])
        self.assertTrue(result["blocked"])
        self.assertIn("truncated", result["error"])
        self.assertLess(len(result["error"]), 400)


if __name__ == "__main__":
    unittest.main()
