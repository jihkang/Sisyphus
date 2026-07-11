# Plan

## Implementation Plan

1. Inspect the current code path related to: Add indexed workflow candidate selection.
2. Implement the requested behavior for: Implement the remaining workflow polling performance remediation without changing lifecycle behavior. Replace run_workflow_cycle's full normalized task-record scan plus per-task reload with a persistent mtime/ctime/size candidate index that stores only minimal scheduling projections and reparses task JSON only when a file is new or changed. Keep a cold-start rebuild and safe recovery from a missing, stale-version, malformed, or partially invalid index. Detect task creation, deletion, and direct external task.json edits on the next cycle. Use the exact existing no-op guards for auto_loop_enabled, closed status, blocked phases, and plan approval so non-candidates are skipped before _advance_task while every prior actionable task remains eligible and deterministically ordered by updated_at then id. Store the derived index atomically in an ignored .planning cache path and keep it non-authoritative. Add deterministic performance regression tests proving a warm scan of hundreds of unchanged closed tasks does not re-read their JSON, plus correctness tests for reactivation, deletion, malformed records/index recovery, ordering, and workflow integration. Update architecture documentation and run the full test, branch coverage, lock, build, Sisyphus verify, CI, PR, merge receipt, and close workflow..
3. Update tests and task docs to match the final behavior.

## Risks

- The conversation request may omit edge conditions that still matter in the current codebase.
- The change may affect adjacent flows if the requested behavior touches shared state.

## Design Evaluation

- Design Mode: `none`
- Decision Reason: `existing contract only`
- Confidence: `medium`
- Layer Impact: `layer-preserving`
- Layer Decision Reason: `n/a`
- Required Design Artifacts: `none`

## Design Artifacts

- Connection Diagram: `n/a`
- Sequence Diagram: `n/a`
- Boundary Note: `n/a`

## Test Strategy

### Normal Cases

- [ ] Requested conversation workflow succeeds

### Edge Cases

- [ ] Minimal valid input still behaves predictably

### Exception Cases

- [ ] Unexpected failure surfaces an actionable error

## Verification Mapping

- `Requested conversation workflow succeeds` -> `sisyphus verify`
- `Minimal valid input still behaves predictably` -> `targeted regression test`
- `Unexpected failure surfaces an actionable error` -> `manual review`

## External LLM Review

- Required: `no`
- Provider: `n/a`
- Purpose: `n/a`
- Trigger: `n/a`
