# Brief

## Task

- Task ID: `TF-20260420-feature-add-end-to-end-tests-for-evolution-artifact-cycle`
- Type: `feature`
- Slug: `add-end-to-end-tests-for-evolution-artifact-cycle`
- Branch: `feat/add-end-to-end-tests-for-evolution-artifact-cycle`

## Problem

- The evolution stack now has focused unit coverage for individual slices, but it still lacks a coherent repo-local vertical test that proves the artifact cycle hangs together across module boundaries.
- Without an end-to-end artifact-cycle test, regressions can slip in where run lineage, follow-up linkage, receipt projection, verification projection, promotion decisions, and invalidation rules still pass in isolation but no longer compose correctly.
- This slice should add tests and test-only helpers only. It must not introduce new runtime surfaces or orchestration behavior.

## Desired Outcome

- A repo-local vertical test exercises read-only run orchestration, isolated candidate materialization, follow-up bridge lineage, receipt/verification projection, promotion decision recording, and invalidation evaluation in one coherent flow.
- The test suite also covers a blocked or stale path so the artifact cycle is validated in both promotion and invalidation directions.
- Any helper added for the tests remains test-scoped and does not widen runtime behavior.

## Acceptance Criteria

- [ ] Add at least one happy-path repo-local integration test that links run orchestration, isolated materialization, follow-up bridge, receipt/verification projection, promotion-gate evaluation, and decision-envelope recording.
- [ ] Add at least one blocked or stale-path test that proves invalidation logic composes with the same artifact lineage instead of being tested only in isolation.
- [ ] The new tests assert stable lineage across run ID, candidate ID, follow-up task ID, artifact refs, and emitted evolution event envelopes.
- [ ] The slice stays test-only and does not add new runtime APIs, CLI commands, or MCP tools.

## Constraints

- Preserve existing repository conventions unless the task requires a deliberate change.
- Re-read the task docs before verify and close.
- Keep implementation confined to tests and test fixtures/helpers.
- Reuse existing evolution modules rather than introducing alternate control paths just for testing.
