# Brief

## Task

- Task ID: `TF-20260420-feature-add-evolution-execution-ingress-surface`
- Type: `feature`
- Slug: `add-evolution-execution-ingress-surface`
- Branch: `feat/add-evolution-execution-ingress-surface`

## Problem

- `execute_evolution_run(...)` already exists inside the evolution package, but operator-facing surfaces only expose persisted run inspection.
- CLI currently supports `evolution run/status/report/compare` for existing runs only.
- MCP currently supports `sisyphus.evolution_run/status/report/compare` for persisted runs only.
- There is no reviewable ingress that starts a new read-only evolution run, persists artifacts, and returns stable run metadata through the user-facing surfaces.

## Desired Outcome

- CLI and MCP can start a new read-only evolution run by calling the existing orchestrator safely.
- The ingress returns reviewable output that includes run identity and artifact location, while preserving the existing read-only boundary against live repo mutation.
- The slice remains bounded to run execution ingress only and does not add follow-up approval, production provider execution, promotion policy mutation, or live task state mutation.

## Acceptance Criteria

- [x] CLI adds a bounded `evolution execute` entrypoint that invokes `execute_evolution_run(...)` and prints reviewable run output for the newly created run.
- [x] MCP adds a bounded `sisyphus.evolution_execute` tool that invokes the same path and returns run metadata plus rendered review content.
- [x] Success and failure paths preserve read-only semantics: append-only run artifacts may be written under `.planning/evolution/runs/<run_id>/`, but live task state, provider execution, approval, and promotion writes remain untouched.
- [x] Regression tests cover success, explicit selection input, and actionable failure reporting for the new ingress surface.

## Constraints

- Preserve existing repository conventions unless the task requires a deliberate change.
- Re-read the task docs before verify and close.
- Do not rename the existing read-only `evolution run/status/report/compare` surfaces.
- Do not add follow-up task creation, plan approval, spec freeze, provider execution, or promotion/invalidation mutation in this slice.
