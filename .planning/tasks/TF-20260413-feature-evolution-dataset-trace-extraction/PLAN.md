# Plan

## Implementation Plan

1. Add `src/taskflow/evolution/dataset.py` with explicit dataclasses for task traces, verify-result traces, event traces, and the aggregate dataset container.
2. Implement a read-only dataset builder that loads task records via existing taskflow helpers, summarizes conformance, copies verify metadata, and reads the configured JSONL event log.
3. Support explicit task-id filtering so later harness work can evaluate a narrowed slice of repository history deterministically.
4. Add focused tests for default extraction, filtering behavior, unknown task rejection, and non-mutating repository reads.
5. Update task docs and verify the slice with targeted unit tests.

## Risks

- If event-task association rules are too loose, later harness inputs may include irrelevant events.
- If the dataset shape omits key trace metadata now, future harness/reporting slices will need avoidable churn.

## Test Strategy

### Normal Cases

- [x] Dataset extraction returns task traces with verify metadata and conformance-derived counts.
- [x] Dataset extraction returns recent event traces from the configured repository event log.

### Edge Cases

- [x] Explicit task-id filtering narrows both tasks and associated events while preserving deterministic ordering.

### Exception Cases

- [x] Unknown task ids are rejected, and dataset extraction does not mutate repository files.

## Verification Mapping

- `Dataset extraction returns task traces with verify metadata and conformance-derived counts.` -> `./.venv/bin/python -m unittest tests.test_evolution -v`
- `Dataset extraction returns recent event traces from the configured repository event log.` -> `./.venv/bin/python -m unittest tests.test_evolution -v`
- `Explicit task-id filtering narrows both tasks and associated events while preserving deterministic ordering.` -> `./.venv/bin/python -m unittest tests.test_evolution -v`
- `Unknown task ids are rejected, and dataset extraction does not mutate repository files.` -> `./.venv/bin/python -m unittest tests.test_evolution -v`

## External LLM Review

- Required: `no`
- Provider: `n/a`
- Purpose: `n/a`
- Trigger: `n/a`
