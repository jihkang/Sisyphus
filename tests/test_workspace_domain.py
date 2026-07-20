from __future__ import annotations

import unittest

from sisyphus.domain.agent.workspace import WorkspaceExecutionState


class WorkspaceExecutionStateTests(unittest.TestCase):
    def test_completion_requires_baseline_mutation_and_later_passing_test(self) -> None:
        state = WorkspaceExecutionState()

        self.assertEqual(state.record_test(1, passed=False), "run_baseline_tests")
        state.record_mutation(2, ("app.py",))
        before_test = state.evaluate_completion(("app.py",))
        self.assertFalse(before_test.completion_ready)
        self.assertIn("passing test", before_test.reason)

        self.assertEqual(state.record_test(3, passed=True), "rerun_tests")
        completed = state.evaluate_completion(("app.py",))
        self.assertTrue(completed.completion_ready)
        self.assertEqual(completed.changed_files, ("app.py",))

    def test_completion_excludes_preexisting_and_reverted_changes(self) -> None:
        state = WorkspaceExecutionState()
        state.record_test(1, passed=True)
        state.record_mutation(2, ("app.py",))
        state.record_test(3, passed=True)

        completion = state.evaluate_completion(("tests/preexisting.py",))

        self.assertFalse(completion.completion_ready)
        self.assertEqual(completion.changed_files, ())


if __name__ == "__main__":
    unittest.main()
