# Plan

## Implementation Plan

1. Align the replay task to the current root-adopted baseline so the read-only orchestrator is defined in the canonical `sisyphus` tree rather than an older task worktree snapshot.
2. Implement the orchestrator entrypoint that composes the existing read-only evolution helpers in one explicit sequence.
   - `plan_evolution_run`
   - `build_evolution_dataset`
   - harness planning
   - constraints evaluation
   - fitness evaluation
   - report generation
3. Create the run artifact directory under `.planning/evolution/runs/<run_id>/` and persist stage outputs as append-only artifacts.
4. Persist stage-aware failure metadata when a step fails so the stopping point and partial artifacts remain inspectable.
5. Add or adjust tests to lock the no-live-mutation guarantee and the expected artifact persistence behavior.

## Hard Risks

- If the orchestrator writes outside `.planning/evolution/runs/<run_id>/`, it will violate the read-only boundary and contaminate live repo state.
- If the orchestrator silently calls provider or follow-up execution paths, it will collapse the authority boundary before the bridge contract is frozen.
- If failure artifacts are not persisted, later debugging and operator review will still depend on transient logs.

## Safety Invariants

- The orchestrator may only write append-only artifacts under `.planning/evolution/runs/<run_id>/`.
- The orchestrator must not modify `src/`, `templates/`, provider configuration, or `.planning/tasks/<live_task_id>/`.
- The orchestrator must not call `provider_wrapper`, request follow-up tasks, or record promotion decisions.
- Constraints or fitness that cannot be computed yet must remain explicit pending states rather than fabricated pass/fail values.

## Out Of Scope

- Candidate materialization.
- Actual harness execution.
- Follow-up bridge execution.
- Promotion or invalidation recording.
- CLI or MCP evolution surface.

## Evidence Requirements

- Persisted run artifacts under `.planning/evolution/runs/<run_id>/`.
- Stage-aware failure artifact or metadata when the run stops early.
- Regression coverage for append-only persistence and no-live-mutation guarantees.

## Failure And Recovery

- If any stage writes outside the run artifact directory, stop and fix the boundary before plan approval.
- If a stage cannot compute constraints or fitness yet, record an explicit pending result instead of inventing a synthetic pass/fail outcome.
- If a failure cannot preserve stage identity and partial outputs, revise the failure model before plan approval.

## Test Strategy

### Normal Cases

- [ ] A read-only evolution run completes the full helper sequence and persists the expected stage artifacts.

### Edge Cases

- [ ] Constraints or fitness that lack metrics remain explicit pending results while the run still persists inspectable artifacts.

### Exception Cases

- [ ] A stage failure persists stage-aware failure metadata and does not mutate live repo or task state.

## Verification Mapping

- `A read-only evolution run completes the full helper sequence and persists the expected stage artifacts.` -> `targeted unit test in tests.test_evolution`
- `Constraints or fitness that lack metrics remain explicit pending results while the run still persists inspectable artifacts.` -> `targeted unit test in tests.test_evolution`
- `A stage failure persists stage-aware failure metadata and does not mutate live repo or task state.` -> `targeted unit test in tests.test_evolution`

## External LLM Review

- Required: `no`
- Provider: `n/a`
- Purpose: `n/a`
- Trigger: `n/a`
