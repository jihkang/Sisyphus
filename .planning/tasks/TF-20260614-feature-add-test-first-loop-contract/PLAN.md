# Plan

## Implementation Plan

1. Inspect `episode_trace`, `eval.loop`, and CLI handling.
2. Add a `test_first` module with stable phase names and a deterministic evaluator over recorded episode steps.
3. Support explicit phase annotations from `action.test_first_phase`, `action.arguments.test_first_phase`, or `result.test_first_phase`.
4. Classify status as `satisfied`, `incomplete`, `violated`, or `not_recorded` without inventing evidence.
5. Replace the eval loop's static `test_first.status = todo` with the evaluator output.
6. Add `sisyphus eval test-first <task-id> [--episode-id] [--json]`.
7. Add tests for satisfied, incomplete, violated, and not-recorded episodes plus CLI parsing.

## Risks

- The conversation request may omit edge conditions that still matter in the current codebase.
- The change may affect adjacent flows if the requested behavior touches shared state.

## Design Evaluation

- Design Mode: `none`
- Decision Reason: `existing contract only`
- Confidence: `medium`
- Layer Impact: `layer-preserving`
- Layer Decision Reason: `n/a`
- Required Design Artifacts: `none`

## Design Artifacts

- Connection Diagram: `n/a`
- Sequence Diagram: `n/a`
- Boundary Note: `n/a`

## Test Strategy

### Normal Cases

- [x] A correctly ordered recorded episode is marked `satisfied`.
- [x] Eval loop JSON includes the evaluated test-first result.

### Edge Cases

- [x] Missing episode steps are marked `not_recorded`.
- [x] Partially annotated steps are marked `incomplete` with missing phases.

### Exception Cases

- [x] Implementation before baseline test is marked `violated`.
- [x] Unknown phase annotations are reported as violations.

## Verification Mapping

- `Satisfied/incomplete/violated/not-recorded phase checks` -> `tests.test_test_first`
- `Eval loop includes test-first evaluator result` -> `tests.test_eval_loop`
- `CLI parser accepts eval test-first surface` -> `tests.test_sisyphus`
- `Full repository behavior remains intact` -> `python -m unittest discover -s tests -v`

## External LLM Review

- Required: `no`
- Provider: `n/a`
- Purpose: `n/a`
- Trigger: `n/a`
