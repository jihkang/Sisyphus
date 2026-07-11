# Brief

## Task

- Task ID: `TF-20260711-feature-add-indexed-workflow-candidate-selection`
- Type: `feature`
- Slug: `add-indexed-workflow-candidate-selection`
- Branch: `feat/add-indexed-workflow-candidate-selection`

## Problem

- Add indexed workflow candidate selection
- Original request: Implement the remaining workflow polling performance remediation without changing lifecycle behavior. Replace run_workflow_cycle's full normalized task-record scan plus per-task reload with a persistent mtime/ctime/size candidate index that stores only minimal scheduling projections and reparses task JSON only when a file is new or changed. Keep a cold-start rebuild and safe recovery from a missing, stale-version, malformed, or partially invalid index. Detect task creation, deletion, and direct external task.json edits on the next cycle. Use the exact existing no-op guards for auto_loop_enabled, closed status, blocked phases, and plan approval so non-candidates are skipped before _advance_task while every prior actionable task remains eligible and deterministically ordered by updated_at then id. Store the derived index atomically in an ignored .planning cache path and keep it non-authoritative. Add deterministic performance regression tests proving a warm scan of hundreds of unchanged closed tasks does not re-read their JSON, plus correctness tests for reactivation, deletion, malformed records/index recovery, ordering, and workflow integration. Update architecture documentation and run the full test, branch coverage, lock, build, Sisyphus verify, CI, PR, merge receipt, and close workflow.

## Desired Outcome

- The repository behavior matches the requested conversation outcome.
- The resulting change stays scoped to this task branch and worktree.

## Acceptance Criteria

- [ ] The requested workflow is implemented or corrected.
- [ ] The task docs reflect the actual implementation and verification scope.
- [ ] Verification notes are ready to be updated after implementation.

## Constraints

- Preserve existing repository conventions unless the task requires a deliberate change.
- Re-read the task docs before verify and close.
