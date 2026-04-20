# Plan

## Implementation Plan

1. Inspect the existing evolution handoff contract, task request API, and daemon task hydration path to identify where follow-up lineage, evidence, and verification obligations should be attached.
2. Implement a bridge layer that converts `EvolutionFollowupRequest` into a reviewable Sisyphus task request using `request_task(..., auto_run=False)` plus explicit evolution source metadata.
3. Ensure the bridge preserves hard boundaries by refusing any request that attempts to permit plan approval, spec freeze, execution, or promotion.
4. Add focused tests for successful request creation, metadata/evidence attachment, and negative cases where privileged bridge behavior is rejected.
5. Update task docs and verification notes to reflect the final bridge behavior.

## Risks

- The existing `followup_of_task_id` hook is driven by duplicate closed-task slugs, which is not sufficient for evolution-originated follow-up lineage on its own.
- If the bridge leaks into `approve_task_plan`, `freeze_task_spec`, or `run_provider_wrapper`, it violates the authority boundary that this slice is meant to protect.
- Evidence summaries and verification obligations must be preserved in a stable shape so later promotion/verification slices can consume them without rewriting the bridge contract.

## Test Strategy

### Normal Cases

- [ ] A valid `EvolutionFollowupRequest` creates a new Sisyphus task with evolution lineage, evidence summary, and verification obligations attached in request metadata.
- [ ] The created follow-up task stays in the normal reviewable lifecycle state (`plan_in_review` / draft spec) because the bridge only requests work.

### Edge Cases

- [ ] Duplicate evidence summaries or owned paths are normalized into a stable, deduped request payload without broadening scope.
- [ ] Follow-up requests with explicit review gates preserve the declared gate order instead of defaulting silently to a wider execution path.

### Exception Cases

- [ ] Any follow-up request that sets `permits_plan_approval`, `permits_spec_freeze`, `permits_execution`, or `permits_promotion` fails with an actionable error and does not create a task.
- [ ] Missing required evidence or verification obligations fails loudly instead of emitting an under-specified task request.

## Verification Mapping

- `A valid EvolutionFollowupRequest creates a new Sisyphus task with evolution lineage, evidence summary, and verification obligations attached in request metadata.` -> `env PYTHONDONTWRITEBYTECODE=1 /tmp/sisyphus-venv-fresh/bin/python -m unittest -q tests.test_evolution`
- `The created follow-up task stays in the normal reviewable lifecycle state (plan_in_review / draft spec) because the bridge only requests work.` -> `env PYTHONDONTWRITEBYTECODE=1 /tmp/sisyphus-venv-fresh/bin/python -m unittest -q tests.test_evolution`
- `Duplicate evidence summaries or owned paths are normalized into a stable, deduped request payload without broadening scope.` -> `env PYTHONDONTWRITEBYTECODE=1 /tmp/sisyphus-venv-fresh/bin/python -m unittest -q tests.test_evolution`
- `Follow-up requests with explicit review gates preserve the declared gate order instead of defaulting silently to a wider execution path.` -> `env PYTHONDONTWRITEBYTECODE=1 /tmp/sisyphus-venv-fresh/bin/python -m unittest -q tests.test_evolution`
- `Any follow-up request that sets permits_plan_approval, permits_spec_freeze, permits_execution, or permits_promotion fails with an actionable error and does not create a task.` -> `env PYTHONDONTWRITEBYTECODE=1 /tmp/sisyphus-venv-fresh/bin/python -m unittest -q tests.test_evolution`
- `Missing required evidence or verification obligations fails loudly instead of emitting an under-specified task request.` -> `env PYTHONDONTWRITEBYTECODE=1 /tmp/sisyphus-venv-fresh/bin/python -m unittest -q tests.test_evolution`

## External LLM Review

- Required: `no`
- Provider: `n/a`
- Purpose: `n/a`
- Trigger: `n/a`
