from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from sisyphus.providers.local_agent import LocalCodingAgent, parse_model_action
from sisyphus.providers.local_openai import (
    LocalProviderConfig,
    LocalProviderConfigError,
    MAX_MODEL_RESPONSE_BYTES,
    OpenAICompatibleClient,
    parse_local_provider_args,
)
from sisyphus.providers.workspace import WorkspaceExecutor


class ScriptedClient:
    def __init__(self, responses: list[str]) -> None:
        self.responses = list(responses)
        self.calls: list[list[dict[str, str]]] = []

    def complete(self, messages: list[dict[str, str]]) -> str:
        self.calls.append([dict(message) for message in messages])
        if not self.responses:
            raise AssertionError("scripted client ran out of responses")
        return self.responses.pop(0)


class LocalProviderConfigTests(unittest.TestCase):
    def test_gemma_defaults_are_machine_neutral(self) -> None:
        config = parse_local_provider_args("gemma", [], env={})

        self.assertEqual(config.base_url, "http://127.0.0.1:8080/v1")
        self.assertEqual(config.model, "gemma-12b")
        self.assertEqual(config.fallback_provider, "codex")
        self.assertGreater(config.max_steps, 0)
        self.assertGreater(config.context_window_tokens, config.context_reserve_tokens)
        self.assertNotIn("/Users/", " ".join(config.test_commands))

    def test_provider_args_override_limits_and_commands(self) -> None:
        config = parse_local_provider_args(
            "local-openai",
            [
                "--base-url",
                "http://127.0.0.1:9000/v1/",
                "--model",
                "local-test",
                "--max-steps",
                "7",
                "--max-protocol-errors",
                "2",
                "--context-window",
                "4096",
                "--context-reserve",
                "512",
                "--compact-ratio",
                "0.6",
                "--test-command",
                "python -m unittest tests.test_app",
                "--no-fallback",
            ],
            env={},
        )

        self.assertEqual(config.base_url, "http://127.0.0.1:9000/v1")
        self.assertEqual(config.model, "local-test")
        self.assertEqual(config.max_steps, 7)
        self.assertEqual(config.max_protocol_errors, 2)
        self.assertEqual(config.context_window_tokens, 4096)
        self.assertEqual(config.context_reserve_tokens, 512)
        self.assertEqual(config.compact_ratio, 0.6)
        self.assertEqual(config.test_commands, ("python -m unittest tests.test_app",))
        self.assertIsNone(config.fallback_provider)

    def test_invalid_context_budget_is_rejected(self) -> None:
        with self.assertRaisesRegex(LocalProviderConfigError, "context reserve"):
            parse_local_provider_args(
                "gemma",
                ["--context-window", "512", "--context-reserve", "512"],
                env={},
            )

    def test_invalid_provider_argument_is_reported_without_system_exit(self) -> None:
        with self.assertRaisesRegex(LocalProviderConfigError, "max-steps"):
            parse_local_provider_args("gemma", ["--max-steps", "not-an-integer"], env={})

    def test_client_posts_openai_compatible_json(self) -> None:
        captured: dict[str, object] = {}

        class Response:
            def __enter__(self) -> Response:
                return self

            def __exit__(self, *args: object) -> None:
                return None

            def read(self, _size: int = -1) -> bytes:
                return json.dumps(
                    {"choices": [{"message": {"content": '{"action":"list_files"}'}}]}
                ).encode("utf-8")

        def fake_urlopen(http_request, timeout):
            captured["url"] = http_request.full_url
            captured["payload"] = json.loads(http_request.data.decode("utf-8"))
            captured["timeout"] = timeout
            return Response()

        config = parse_local_provider_args(
            "gemma",
            ["--base-url", "http://127.0.0.1:9999/v1", "--model", "gemma-test"],
            env={},
        )
        client = OpenAICompatibleClient(config)

        with mock.patch("sisyphus.providers.local_openai.request.urlopen", side_effect=fake_urlopen):
            content = client.complete([{"role": "user", "content": "task"}])

        self.assertEqual(content, '{"action":"list_files"}')
        self.assertEqual(captured["url"], "http://127.0.0.1:9999/v1/chat/completions")
        payload = captured["payload"]
        self.assertEqual(payload["model"], "gemma-test")
        self.assertEqual(payload["messages"], [{"role": "user", "content": "task"}])
        self.assertEqual(payload["response_format"], {"type": "json_object"})

    def test_client_reports_endpoint_and_invalid_json_failures(self) -> None:
        config = parse_local_provider_args("gemma", [], env={})
        client = OpenAICompatibleClient(config)

        with mock.patch(
            "sisyphus.providers.local_openai.request.urlopen",
            side_effect=TimeoutError("timed out"),
        ):
            with self.assertRaisesRegex(RuntimeError, "start an OpenAI-compatible local server"):
                client.complete([{"role": "user", "content": "task"}])

        class InvalidResponse:
            def __enter__(self) -> InvalidResponse:
                return self

            def __exit__(self, *args: object) -> None:
                return None

            def read(self, _size: int = -1) -> bytes:
                return b"not-json"

        with mock.patch(
            "sisyphus.providers.local_openai.request.urlopen",
            return_value=InvalidResponse(),
        ):
            with self.assertRaisesRegex(RuntimeError, "invalid JSON"):
                client.complete([{"role": "user", "content": "task"}])

        class OversizedResponse(InvalidResponse):
            def read(self, _size: int = -1) -> bytes:
                return b"x" * (MAX_MODEL_RESPONSE_BYTES + 1)

        with mock.patch(
            "sisyphus.providers.local_openai.request.urlopen",
            return_value=OversizedResponse(),
        ):
            with self.assertRaisesRegex(RuntimeError, "response exceeds"):
                client.complete([{"role": "user", "content": "task"}])


class WorkspaceExecutorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)
        (self.root / "tests").mkdir()
        (self.root / "app.py").write_text(
            "def add(left, right):\n    return left - right\n",
            encoding="utf-8",
        )
        (self.root / "tests" / "test_app.py").write_text(
            "import unittest\n\n"
            "from app import add\n\n\n"
            "class AddTests(unittest.TestCase):\n"
            "    def test_adds(self):\n"
            "        self.assertEqual(add(2, 3), 5)\n",
            encoding="utf-8",
        )
        self._git("init", "-b", "main")
        self._git("config", "user.email", "test@example.com")
        self._git("config", "user.name", "Test User")
        self._git("add", ".")
        self._git("commit", "-m", "initial")
        self.executor = WorkspaceExecutor(
            self.root,
            owned_paths=("app.py", "tests"),
            test_commands=(f"{sys.executable} -m unittest discover -s tests",),
            command_timeout_seconds=10.0,
            max_output_chars=4000,
        )

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

    def test_read_search_and_list_are_bounded(self) -> None:
        listed = self.executor.execute({"action": "list_files"}, step=1)
        read = self.executor.execute({"action": "read_file", "path": "app.py"}, step=2)
        search = self.executor.execute({"action": "search", "query": "return left"}, step=3)

        self.assertTrue(listed["ok"])
        self.assertIn("app.py", listed["output"])
        self.assertTrue(read["ok"])
        self.assertIn("return left - right", read["output"])
        self.assertTrue(search["ok"])
        self.assertIn("app.py:2", search["output"])

    def test_read_search_and_test_outputs_are_actually_truncated(self) -> None:
        long_path = self.root / "long.txt"
        long_path.write_text(("needle " + ("x" * 80) + "\n") * 30, encoding="utf-8")
        executor = WorkspaceExecutor(
            self.root,
            test_commands=('python3 -c "print(\'x\' * 2000)"',),
            max_output_chars=256,
        )

        read = executor.execute({"action": "read_file", "path": "long.txt"}, step=1)
        search = executor.execute({"action": "search", "query": "needle"}, step=2)
        tested = executor.execute({"action": "run_test", "command_id": 0}, step=3)

        self.assertIn("truncated", read["output"])
        self.assertIn("truncated", search["output"])
        self.assertTrue(tested["ok"])
        self.assertIn("truncated", tested["output"])

    def test_path_traversal_protected_and_out_of_scope_writes_are_rejected(self) -> None:
        outside = self.executor.execute(
            {"action": "write_file", "path": "../outside.py", "content": "bad"},
            step=1,
        )
        protected = self.executor.execute(
            {"action": "write_file", "path": ".planning/task.json", "content": "bad"},
            step=2,
        )
        unowned = self.executor.execute(
            {"action": "write_file", "path": "README.md", "content": "bad"},
            step=3,
        )

        self.assertFalse(outside["ok"])
        self.assertTrue(outside["blocked"])
        self.assertFalse(protected["ok"])
        self.assertTrue(protected["blocked"])
        self.assertFalse(unowned["ok"])
        self.assertTrue(unowned["blocked"])
        self.assertFalse((self.root.parent / "outside.py").exists())

    def test_symlink_escape_is_rejected(self) -> None:
        outside_dir = self.root.parent / f"{self.root.name}-outside"
        outside_dir.mkdir()
        self.addCleanup(lambda: outside_dir.rmdir() if outside_dir.exists() else None)
        (self.root / "tests" / "escape").symlink_to(outside_dir, target_is_directory=True)

        result = self.executor.execute(
            {"action": "write_file", "path": "tests/escape/bad.py", "content": "bad"},
            step=1,
        )

        self.assertFalse(result["ok"])
        self.assertTrue(result["blocked"])
        self.assertFalse((outside_dir / "bad.py").exists())

    def test_oversized_file_read_is_rejected_before_loading_content(self) -> None:
        path = self.root / "large.bin"
        path.write_bytes(b"x" * 1_000_001)

        result = self.executor.execute(
            {"action": "read_file", "path": "large.bin"},
            step=1,
        )

        self.assertFalse(result["ok"])
        self.assertTrue(result["blocked"])
        self.assertIn("read limit", result["error"])

    def test_patch_test_and_completion_order_are_enforced(self) -> None:
        patch = """diff --git a/app.py b/app.py
--- a/app.py
+++ b/app.py
@@ -1,2 +1,2 @@
 def add(left, right):
-    return left - right
+    return left + right
"""
        baseline = self.executor.execute({"action": "run_test", "command_id": 0}, step=1)
        changed = self.executor.execute({"action": "apply_patch", "patch": patch}, step=2)

        self.assertFalse(baseline["ok"])
        self.assertEqual(baseline["test_first_phase"], "run_baseline_tests")
        self.assertTrue(changed["ok"])
        before_test = self.executor.completion_facts()
        self.assertFalse(before_test["completion_ready"])
        self.assertIn("passing test", before_test["reason"])

        tested = self.executor.execute({"action": "run_test", "command_id": 0}, step=3)
        self.assertTrue(tested["ok"])
        self.assertTrue(self.executor.completion_facts()["completion_ready"])

        rewritten = self.executor.execute(
            {
                "action": "write_file",
                "path": "app.py",
                "content": "def add(left, right):\n    return left + right  # exact sum\n",
            },
            step=4,
        )
        self.assertTrue(rewritten["ok"])
        self.assertFalse(self.executor.completion_facts()["completion_ready"])

    def test_identical_write_is_a_no_op_and_does_not_move_mutation_order(self) -> None:
        self.executor.execute({"action": "run_test", "command_id": 0}, step=1)
        changed = self.executor.execute(
            {
                "action": "write_file",
                "path": "app.py",
                "content": "def add(left, right):\n    return left + right\n",
            },
            step=2,
        )
        repeated = self.executor.execute(
            {
                "action": "write_file",
                "path": "app.py",
                "content": "def add(left, right):\n    return left + right\n",
            },
            step=3,
        )

        self.assertTrue(changed["mutated"])
        self.assertFalse(repeated["mutated"])
        self.assertTrue(repeated["no_op"])
        self.assertIn("run a configured test", repeated["guidance"])
        self.assertEqual(self.executor.last_mutation_step, 2)

    def test_mutation_before_baseline_test_is_blocked(self) -> None:
        result = self.executor.execute(
            {
                "action": "write_file",
                "path": "app.py",
                "content": "def add(left, right):\n    return left + right\n",
            },
            step=1,
        )

        self.assertFalse(result["ok"])
        self.assertTrue(result["blocked"])
        self.assertIn("baseline test", result["error"])
        self.assertEqual(self.executor.last_mutation_step, None)

    def test_planning_only_change_never_counts_as_code_level_result(self) -> None:
        planning = self.root / ".planning"
        planning.mkdir()
        (planning / "note.md").write_text("model claim\n", encoding="utf-8")

        facts = self.executor.completion_facts()

        self.assertEqual(facts["changed_files"], [])
        self.assertFalse(facts["completion_ready"])
        self.assertIn("non-planning", facts["reason"])

    def test_unrelated_preexisting_diff_cannot_satisfy_completion(self) -> None:
        original = "def add(left, right):\n    return left - right\n"
        test_path = self.root / "tests" / "test_app.py"
        test_path.write_text(test_path.read_text(encoding="utf-8") + "\n# preexisting\n", encoding="utf-8")
        executor = WorkspaceExecutor(
            self.root,
            owned_paths=("app.py",),
            test_commands=(f"{sys.executable} -c pass",),
        )

        executor.execute({"action": "run_test", "command_id": 0}, step=1)
        executor.execute(
            {
                "action": "write_file",
                "path": "app.py",
                "content": "def add(left, right):\n    return left + right\n",
            },
            step=2,
        )
        executor.execute(
            {"action": "write_file", "path": "app.py", "content": original},
            step=3,
        )
        executor.execute({"action": "run_test", "command_id": 0}, step=4)

        facts = executor.completion_facts()
        self.assertFalse(facts["completion_ready"])
        self.assertEqual(facts["changed_files"], [])

    def test_python_test_command_uses_the_worker_interpreter(self) -> None:
        executor = WorkspaceExecutor(
            self.root,
            test_commands=('python3 -c "import sys; print(sys.executable)"',),
        )

        result = executor.execute({"action": "run_test", "command_id": 0}, step=1)

        self.assertTrue(result["ok"])
        self.assertEqual(result["output"].strip(), sys.executable)


class LocalCodingAgentTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)
        (self.root / "tests").mkdir()
        (self.root / "app.py").write_text(
            "def add(left, right):\n    return left - right\n",
            encoding="utf-8",
        )
        (self.root / "tests" / "test_app.py").write_text(
            "import unittest\nfrom app import add\n\n"
            "class AddTests(unittest.TestCase):\n"
            "    def test_adds(self):\n"
            "        self.assertEqual(add(2, 3), 5)\n",
            encoding="utf-8",
        )
        for command in (
            ["git", "init", "-b", "main"],
            ["git", "config", "user.email", "test@example.com"],
            ["git", "config", "user.name", "Test User"],
            ["git", "add", "."],
            ["git", "commit", "-m", "initial"],
        ):
            subprocess.run(command, cwd=self.root, check=True, capture_output=True, text=True)

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def _config(self, **overrides: object) -> LocalProviderConfig:
        values: dict[str, object] = {
            "provider": "gemma",
            "base_url": "http://127.0.0.1:9999/v1",
            "model": "gemma-test",
            "test_commands": (f"{sys.executable} -m unittest discover -s tests",),
            "max_steps": 8,
            "max_protocol_errors": 2,
            "context_window_tokens": 2048,
            "context_reserve_tokens": 256,
            "compact_ratio": 0.8,
            "max_tool_output_chars": 4000,
        }
        values.update(overrides)
        return LocalProviderConfig(**values)

    def _executor(self) -> WorkspaceExecutor:
        return WorkspaceExecutor(
            self.root,
            owned_paths=("app.py", "tests"),
            test_commands=(f"{sys.executable} -m unittest discover -s tests",),
            command_timeout_seconds=10.0,
            max_output_chars=4000,
        )

    def test_parse_model_action_handles_thinking_and_markdown_fence(self) -> None:
        action = parse_model_action(
            '<think>inspect first</think>\n```json\n{"action":"read_file","path":"app.py"}\n```'
        )

        self.assertEqual(action, {"action": "read_file", "path": "app.py"})

    def test_parse_model_action_rejects_unknown_action(self) -> None:
        with self.assertRaisesRegex(ValueError, "unknown local agent action"):
            parse_model_action('{"action":"shell","command":"rm -rf /"}')

    def test_scripted_agent_changes_code_tests_and_completes(self) -> None:
        client = ScriptedClient(
            [
                '{"action":"read_file","path":"app.py"}',
                '{"action":"run_test","command_id":0}',
                json.dumps(
                    {
                        "action": "write_file",
                        "path": "app.py",
                        "content": "def add(left, right):\n    return left + right\n",
                    }
                ),
                '{"action":"run_test","command_id":0}',
                '{"action":"finish","status":"completed","summary":"Fixed addition and tests pass."}',
            ]
        )
        receipt_path = self.root / "receipt.json"
        agent = LocalCodingAgent(
            config=self._config(),
            client=client,
            executor=self._executor(),
            receipt_path=receipt_path,
            observation_hash="sha256:test-observation",
        )

        result = agent.run("Fix add according to the frozen task.")

        self.assertEqual(result.status, "completed")
        self.assertEqual(result.action_count, 5)
        self.assertTrue(result.completion_facts["completion_ready"])
        self.assertEqual(result.completion_facts["changed_files"], ["app.py"])
        self.assertEqual(json.loads(receipt_path.read_text(encoding="utf-8"))["status"], "completed")

    def test_compaction_is_automatic_and_retains_structured_state(self) -> None:
        client = ScriptedClient(
            [
                '{"action":"read_file","path":"app.py"}',
                '{"action":"run_test","command_id":0}',
                json.dumps(
                    {
                        "action": "write_file",
                        "path": "app.py",
                        "content": "def add(left, right):\n    return left + right\n",
                    }
                ),
                '{"action":"run_test","command_id":0}',
                '{"action":"finish","status":"completed","summary":"done"}',
            ]
        )
        agent = LocalCodingAgent(
            config=self._config(
                context_window_tokens=512,
                context_reserve_tokens=128,
                compact_ratio=0.5,
            ),
            client=client,
            executor=self._executor(),
            observation_hash="sha256:compact",
        )

        result = agent.run("Fix the bug. " + ("scope " * 40))

        self.assertEqual(result.status, "completed")
        self.assertGreaterEqual(result.compaction_count, 1)
        rendered_calls = json.dumps(client.calls)
        self.assertIn("COMPACTED_STATE", rendered_calls)
        self.assertIn("app.py", rendered_calls)

    def test_malformed_output_uses_bounded_recovery(self) -> None:
        client = ScriptedClient(
            [
                "not json",
                '{"action":"run_test","command_id":0}',
                json.dumps(
                    {
                        "action": "write_file",
                        "path": "app.py",
                        "content": "def add(left, right):\n    return left + right\n",
                    }
                ),
                '{"action":"run_test","command_id":0}',
                '{"action":"finish","status":"completed","summary":"done"}',
            ]
        )
        agent = LocalCodingAgent(
            config=self._config(),
            client=client,
            executor=self._executor(),
            observation_hash="sha256:retry",
        )

        result = agent.run("Fix add.")

        self.assertEqual(result.status, "completed")
        self.assertEqual(result.protocol_error_count, 1)

    def test_model_response_history_is_bounded_before_the_next_turn(self) -> None:
        client = ScriptedClient(
            [
                ("prefix " * 500) + '{"action":"list_files"}',
                '{"action":"finish","status":"failed","summary":"stop"}',
            ]
        )
        agent = LocalCodingAgent(
            config=self._config(max_steps=2, max_tool_output_chars=256),
            client=client,
            executor=self._executor(),
            observation_hash="sha256:bounded-model-response",
        )

        result = agent.run("Inspect the fixture.")

        self.assertEqual(result.status, "failed")
        second_prompt = json.dumps(client.calls[1])
        self.assertIn("truncated", second_prompt)
        self.assertLess(len(second_prompt), 3000)

    def test_completed_claim_without_change_is_rejected(self) -> None:
        client = ScriptedClient(
            ['{"action":"finish","status":"completed","summary":"implemented"}']
        )
        agent = LocalCodingAgent(
            config=self._config(),
            client=client,
            executor=self._executor(),
            observation_hash="sha256:no-change",
        )

        result = agent.run("Fix add.")

        self.assertEqual(result.status, "failed")
        self.assertIn("non-planning", result.error)

    def test_completed_claim_without_post_change_test_is_rejected(self) -> None:
        client = ScriptedClient(
            [
                '{"action":"run_test","command_id":0}',
                json.dumps(
                    {
                        "action": "write_file",
                        "path": "app.py",
                        "content": "def add(left, right):\n    return left + right\n",
                    }
                ),
                '{"action":"finish","status":"completed","summary":"implemented"}',
            ]
        )
        agent = LocalCodingAgent(
            config=self._config(),
            client=client,
            executor=self._executor(),
            observation_hash="sha256:no-test",
        )

        result = agent.run("Fix add.")

        self.assertEqual(result.status, "failed")
        self.assertIn("passing test", result.error)

    def test_blocked_workspace_action_is_recorded_and_cannot_complete(self) -> None:
        client = ScriptedClient(
            [
                '{"action":"run_test","command_id":0}',
                '{"action":"write_file","path":"../escape.py","content":"bad"}',
                '{"action":"finish","status":"completed","summary":"done"}',
            ]
        )
        agent = LocalCodingAgent(
            config=self._config(),
            client=client,
            executor=self._executor(),
            observation_hash="sha256:blocked",
        )

        result = agent.run("Fix add.")

        self.assertEqual(result.status, "failed")
        self.assertEqual(result.blocked_action_count, 1)
        self.assertFalse((self.root.parent / "escape.py").exists())

    def test_action_budget_exhaustion_returns_an_actionable_failure(self) -> None:
        agent = LocalCodingAgent(
            config=self._config(max_steps=2),
            client=ScriptedClient(
                [
                    '{"action":"list_files"}',
                    '{"action":"read_file","path":"app.py"}',
                ]
            ),
            executor=self._executor(),
            observation_hash="sha256:budget",
        )

        result = agent.run("Fix add.")

        self.assertEqual(result.status, "failed")
        self.assertEqual(result.action_count, 2)
        self.assertIn("exhausted its action budget", result.error)


if __name__ == "__main__":
    unittest.main()
