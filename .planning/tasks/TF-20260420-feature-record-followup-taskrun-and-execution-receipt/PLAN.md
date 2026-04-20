# Plan

## Implementation Plan

1. Inspect the existing evolution follow-up source-context shape, core `TaskRunRef` projection logic, and task-local receipt artifacts (`VERIFY.md`, `last_verify_results`, optional promotion receipt).
2. Implement an evolution receipt projection helper that validates a bridged follow-up task, extracts execution identifiers from verify results, and emits `ExecutionReceiptArtifact` plus `TaskRunRef` data linked to the source evolution run.
3. Reuse real task receipt locators where possible: task verify resource/doc for verify-command runs and the promotion receipt path when that file exists.
4. Add focused tests for successful projection, optional promotion receipt inclusion, and failure cases where the follow-up task has no verify results or references a missing receipt.
5. Update task docs and verification notes to match the implemented receipt-linkage behavior.

## Risks

- `last_verify_results` lives in task state rather than a standalone receipt file, so the mapper must choose a stable locator scheme that points to real task artifacts.
- If the mapper accepts tasks without evolution follow-up lineage in source context, it will blur the boundary between normal Sisyphus tasks and evolution-managed follow-up tasks.
- Promotion receipts are optional; the mapper must include them when present but must not require them for ordinary executed follow-up tasks.

## Test Strategy

### Normal Cases

- [ ] An executed evolution follow-up task with verify results projects into `ExecutionReceiptArtifact` entries and `TaskRunRef` records tied to the source evolution run.
- [ ] A follow-up task with a recorded promotion receipt adds that receipt as an additional execution receipt artifact without changing the derived verify task runs.

### Edge Cases

- [ ] Verify-command receipt locators remain stable and task-relative even when the task directory is nested under `.planning/tasks/<task-id>/`.
- [ ] Receipt linkage ignores unrelated task metadata and only reads the evolution follow-up source-context segment.

### Exception Cases

- [ ] A bridged follow-up task with no verify results fails clearly instead of fabricating task-run linkage.
- [ ] A task that claims to have a promotion receipt but lacks the referenced file fails with an actionable missing-receipt error.

## Verification Mapping

- `An executed evolution follow-up task with verify results projects into ExecutionReceiptArtifact entries and TaskRunRef records tied to the source evolution run.` -> `env PYTHONDONTWRITEBYTECODE=1 /tmp/sisyphus-venv-fresh/bin/python -m unittest -q tests.test_evolution`
- `A follow-up task with a recorded promotion receipt adds that receipt as an additional execution receipt artifact without changing the derived verify task runs.` -> `env PYTHONDONTWRITEBYTECODE=1 /tmp/sisyphus-venv-fresh/bin/python -m unittest -q tests.test_evolution`
- `Verify-command receipt locators remain stable and task-relative even when the task directory is nested under .planning/tasks/<task-id>/.` -> `env PYTHONDONTWRITEBYTECODE=1 /tmp/sisyphus-venv-fresh/bin/python -m unittest -q tests.test_evolution`
- `Receipt linkage ignores unrelated task metadata and only reads the evolution follow-up source-context segment.` -> `env PYTHONDONTWRITEBYTECODE=1 /tmp/sisyphus-venv-fresh/bin/python -m unittest -q tests.test_evolution`
- `A bridged follow-up task with no verify results fails clearly instead of fabricating task-run linkage.` -> `env PYTHONDONTWRITEBYTECODE=1 /tmp/sisyphus-venv-fresh/bin/python -m unittest -q tests.test_evolution`
- `A task that claims to have a promotion receipt but lacks the referenced file fails with an actionable missing-receipt error.` -> `env PYTHONDONTWRITEBYTECODE=1 /tmp/sisyphus-venv-fresh/bin/python -m unittest -q tests.test_evolution`

## External LLM Review

- Required: `no`
- Provider: `n/a`
- Purpose: `n/a`
- Trigger: `n/a`
