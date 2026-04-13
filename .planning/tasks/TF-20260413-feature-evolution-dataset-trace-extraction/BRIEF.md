# Brief

## Task

- Task ID: `TF-20260413-feature-evolution-dataset-trace-extraction`
- Type: `feature`
- Slug: `evolution-dataset-trace-extraction`
- Branch: `feat/evolution-dataset-trace-extraction`

## Problem

- The self-evolution plan requires a dataset builder that mines repository-local traces, but `taskflow.evolution.dataset` does not exist yet.
- The next safe slice is to extract task, conformance, verify, and event-log traces into a stable in-memory dataset without running candidates or mutating live state.
- Later harness and MCP work need a predictable dataset shape to consume.

## Desired Outcome

- `src/taskflow/evolution/dataset.py` can build a read-only dataset from existing repository-local traces.
- The dataset includes task-level verify metadata, conformance summaries/history counts, and recent event-log entries.
- Callers can optionally scope dataset extraction to a subset of task ids.

## Acceptance Criteria

- [x] A dataset module exists under `taskflow.evolution` and exports a stable read-only dataset shape.
- [x] Dataset extraction includes task traces, verify results, conformance summaries/history-derived counts, and recent event traces.
- [x] Explicit task-id filtering narrows both task traces and associated event traces.
- [x] Dataset extraction rejects unknown task ids and does not mutate repository state.

## Constraints

- Keep scope to read-only extraction; do not add harness execution, candidate mutation, reporting, or MCP evolution resources/tools here.
- Use existing repository-local sources only: task records plus the configured event log path.
- Preserve the control-plane boundary by avoiding writes to live `.planning` state.
