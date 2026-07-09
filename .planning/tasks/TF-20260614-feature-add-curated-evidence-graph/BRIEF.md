# Brief

## Task

- Task ID: `TF-20260614-feature-add-curated-evidence-graph`
- Type: `feature`
- Slug: `add-curated-evidence-graph`
- Branch: `feat/add-curated-evidence-graph`

## Problem

- `VERIFY.md` is human-readable, but closeout currently has no structured evidence artifact to inspect.
- Sisyphus needs a verification-centered closeout input that can distinguish supported evidence, partial evidence, unsupported high-importance evidence, and missing evidence.

Scope:
- Define artifacts/evidence/evidence-graph.json or curated-evidence.json schema with claim, source, verdict, importance, reproducibility, observed_at, blocking, linked_subtask, and linked_spec_section fields.
- Extend verify_task to generate or update evidence candidates from command results, conformance status, verification claims, and relevant changeset/diff references.
- Add close_task gates for missing evidence graph, unsupported high-importance claims, and blocking evidence gaps.
- Keep VERIFY.md as human-readable projection; structured evidence is the canonical closeout input.

Acceptance criteria:
- verify_task can persist structured evidence for a passing task.
- close_task blocks when required high-importance evidence is missing or unsupported.
- existing tasks without code changes are not over-gated unnecessarily.
- Tests cover supported, partial, unsupported, and missing evidence cases.

Dependency: should follow lifecycle/action boundary enforcement; trace integration can be parallel but evidence should reuse observation gates where possible.

## Desired Outcome

- `run_verify` writes `artifacts/evidence/evidence-graph.json`.
- `close_task` blocks newly verified tasks when the evidence graph is missing or contains unsupported high-importance blocking evidence.
- Observation and MCP resources expose evidence summary/state for agents without requiring them to infer it from `VERIFY.md`.

## Acceptance Criteria

- [x] Passing verify persists structured curated evidence.
- [x] Close blocks missing evidence for newly verified tasks.
- [x] Close blocks unsupported high-importance evidence and blocking evidence gaps.
- [x] Legacy/manual verified tasks without an explicit evidence requirement are not over-gated.
- [x] `task://<task-id>/evidence` and observation evidence summary expose the artifact state.

## Constraints

- Preserve existing repository conventions unless the task requires a deliberate change.
- Re-read the task docs before verify and close.
- Keep `VERIFY.md` as a human-readable projection; the evidence graph is the structured closeout input.
