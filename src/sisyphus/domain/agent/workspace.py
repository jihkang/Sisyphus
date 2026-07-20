from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class WorkspaceCompletion:
    completion_ready: bool
    reason: str
    changed_files: tuple[str, ...]
    baseline_test_step: int | None
    last_mutation_step: int | None
    last_successful_test_step: int | None


@dataclass(slots=True)
class WorkspaceExecutionState:
    baseline_test_step: int | None = None
    last_mutation_step: int | None = None
    last_successful_test_step: int | None = None
    blocked_action_count: int = 0
    mutated_paths: set[str] = field(default_factory=set)

    def record_mutation(self, step: int, paths: Iterable[str]) -> None:
        self.last_mutation_step = step
        self.mutated_paths.update(str(path) for path in paths)

    def record_test(self, step: int, *, passed: bool) -> str:
        if self.last_mutation_step is None:
            self.baseline_test_step = step
            return "run_baseline_tests"
        if passed:
            self.last_successful_test_step = step
        return "rerun_tests"

    def record_blocked_action(self) -> None:
        self.blocked_action_count += 1

    def evaluate_completion(self, changed_files: Iterable[str]) -> WorkspaceCompletion:
        produced_files = tuple(sorted(set(changed_files).intersection(self.mutated_paths)))
        if not produced_files or self.last_mutation_step is None:
            return self._completion(
                ready=False,
                reason="completed claim requires a non-planning code-level result produced by this run",
                changed_files=produced_files,
            )
        if self.baseline_test_step is None:
            return self._completion(
                ready=False,
                reason="completed claim requires a baseline test before mutation",
                changed_files=produced_files,
            )
        if (
            self.last_successful_test_step is None
            or self.last_successful_test_step <= self.last_mutation_step
        ):
            return self._completion(
                ready=False,
                reason="completed claim requires a passing test after the latest mutation",
                changed_files=produced_files,
            )
        return self._completion(
            ready=True,
            reason="non-planning changes exist and a configured test passed after the latest mutation",
            changed_files=produced_files,
        )

    def _completion(
        self,
        *,
        ready: bool,
        reason: str,
        changed_files: tuple[str, ...],
    ) -> WorkspaceCompletion:
        return WorkspaceCompletion(
            completion_ready=ready,
            reason=reason,
            changed_files=changed_files,
            baseline_test_step=self.baseline_test_step,
            last_mutation_step=self.last_mutation_step,
            last_successful_test_step=self.last_successful_test_step,
        )


__all__ = ["WorkspaceCompletion", "WorkspaceExecutionState"]
