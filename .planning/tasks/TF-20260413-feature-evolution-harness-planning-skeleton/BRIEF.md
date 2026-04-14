# Brief

## Task

- Task ID: `TF-20260413-feature-evolution-harness-planning-skeleton`
- Type: `feature`
- Slug: `evolution-harness-planning-skeleton`
- Branch: `feat/evolution-harness-planning-skeleton`

## Problem

- The self-evolution plan now has a run model and a dataset builder, but there is no harness layer connecting them into a baseline-vs-candidate evaluation plan.
- The next safe slice is not real execution; it is the planning model that declares isolation requirements, candidate scope, and result placeholders without touching live tasks.
- Later harness execution, scoring, and reporting slices need a stable plan/result shape to build on.

## Desired Outcome

- `src/taskflow/evolution/harness.py` can build a read-only evaluation plan from an evolution run plus dataset.
- The harness plan explicitly models baseline and candidate evaluation slots, selected target ids, dataset scope, and isolation requirements.
- Planned result containers exist for later metrics capture, but remain empty/pending in this slice.

## Acceptance Criteria

- [x] A harness module exists under `taskflow.evolution` and exports stable planning/result dataclasses.
- [x] Harness planning pairs a run with a dataset and produces baseline/candidate evaluation slots without live execution.
- [x] Isolation requirements and planned metrics/result containers are explicit in the returned model.
- [x] Harness planning rejects invalid scope combinations and does not mutate repository state.

## Constraints

- Keep scope to harness planning only; do not execute candidates, snapshot branches, or mutate live `.planning` state.
- Preserve the run/dataset boundary established in the previous slices.
- Result containers should be placeholders for future execution, not partially executed artifacts.
