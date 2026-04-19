# Brief

## Task

- Task ID: `TF-20260419-feature-freeze-evolution-authority-boundary-and-safety-rules-root-replay`
- Type: `feature`
- Slug: `freeze-evolution-authority-boundary-and-safety-rules-root-replay`
- Branch: `feat/freeze-evolution-authority-boundary-and-safety-rules-root-replay`

## Problem

- `TF-20260418-feature-freeze-evolution-authority-boundary-and-safety-rules` already defined and verified the authority boundary, but that task is blocked only because its stale task worktree predates the current root source-of-truth.
- The current root worktree now carries the active `taskflow` -> `sisyphus` migration baseline, so the boundary language must be replayed on top of that adopted baseline rather than resumed in the old worktree.
- This follow-up task must preserve the original narrow boundary: authoritative docs and normative safety language only.

## Desired Outcome

- `docs/architecture.md` and `docs/self-evolution-mcp-plan.md` describe `evolution` as the soft-cognition layer and `Sisyphus` as the hard-state layer in clear, normative terms on top of the current root-adopted baseline.
- The docs explicitly distinguish the isolated harness executor from the authoritative Sisyphus execution path.
- The docs state that read-only evolution orchestration may append run artifacts under `.planning/evolution/runs/<run_id>/` but may not mutate live repo files or live task state.

## Acceptance Criteria

- [ ] The docs explicitly state that `evolution` owns planning, candidate comparison, topology-changing judgment, and report synthesis.
- [ ] The docs explicitly state that only `Sisyphus` owns execution authority, task lifecycle, verification, receipts, and promotion/invalidation recording.
- [ ] The docs explicitly state that the harness executor is evaluation-only and may not mutate live task state or self-approve follow-up work.
- [ ] The docs explicitly define the meaning of read-only orchestration as append-only run-artifact persistence under `.planning/evolution/runs/<run_id>/`.

## Constraints

- Limit scope to authoritative docs and boundary language.
- Do not implement runtime behavior changes, executor logic, or promotion flows in this task.
- Re-read the task docs before verify and close.

## Spec Risks

- Ambiguous authority language can let later tasks introduce hidden execution paths outside Sisyphus.
- If the docs blur evaluation and execution, the harness executor can be misused as a production mutation path.
- If read-only is underspecified, later code may incorrectly block run-artifact persistence or incorrectly allow live-state mutation.
