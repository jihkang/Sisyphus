# Brief

## Task

- Task ID: `TF-20260517-feature-add-spec-validation-pipeline`
- Type: `feature`
- Slug: `add-spec-validation-pipeline`
- Branch: `feat/add-spec-validation-pipeline`

## Problem

- Sisyphus currently has shallow spec/doc gates inside `run_verify`, but no dedicated validation stage for generated task specs before plan approval or spec freeze.
- Generic generated docs can be approved or frozen even when they do not define an executable task contract.
- This lets weak specs move into execution, which then makes later verify hardening, MCP repair, agent authority work, search ranking, and evolution work less reliable.
- The first problem to solve is not implementation verification. It is validating that the task definition itself is concrete, scoped, executable, and evidence-ready before work begins.

## Desired Outcome

- Add a deterministic spec validation pipeline that evaluates BRIEF/PLAN/FIX_PLAN/REPRO docs and task metadata before a task can be approved, frozen, or executed.
- Persist a reviewable validation report per task, expose it through CLI and MCP, and make lifecycle gates point to actionable findings.
- Keep the first slice deterministic and repo-local; do not introduce model-based semantic review in this task.

## Acceptance Criteria

- [ ] Sisyphus has a reusable spec validation module that produces a structured report with pass/fail/warning findings.
- [ ] Validation checks required docs, required sections, non-placeholder acceptance criteria, scope/owned path clarity, normal/edge/exception coverage, verification mapping alignment, design mode/layer consistency, external review policy completeness, dependency/backlog references, and explicit waivers for docs-only/design-only work.
- [ ] `plan approve` and `spec freeze` block on failing validation findings and record clear gates.
- [ ] `run_verify` consumes validation state or re-runs validation so execution verification cannot silently pass a weak spec.
- [ ] CLI exposes `sisyphus spec validate <task-id>` with human-readable output and machine-readable JSON output.
- [ ] MCP exposes an equivalent validation tool and a read-only validation report resource.
- [ ] Validation reports are persisted under the task directory and are invalidated or refreshed when source docs change.
- [ ] Focused tests cover passing specs, generated placeholder specs, missing coverage classes, unmapped verification methods, invalid design metadata, missing external review policy details, waiver handling, and lifecycle blocking.

## Constraints

- Preserve existing repository conventions unless the task requires a deliberate change.
- Re-read the task docs before verify and close.
- Do not implement neural or external LLM spec judgment in this slice.
- Do not make legacy frozen tasks retroactively fail unless they are explicitly validated, re-approved, or re-frozen.
- Keep the validator deterministic enough to run in CI and MCP contexts without network access.
