# Plan

## Implementation Plan

1. Inspect existing eval loop, reward, CLI parser, and evolution metric code.
2. Add a benchmark module that loads deterministic fixtures from `benchmarks/tasks/*.json`.
3. Represent the seven requested scenarios and five requested modes without invoking a live agent.
4. Compute stable aggregate metrics: task success, verify pass, close success, false close, conformance green, spec drift detection, evidence completeness, action count, unrelated diff ratio, reproducibility, and human intervention count.
5. Add CLI surface for `sisyphus benchmark run --json` and default Markdown output.
6. Add tests for fixture loading, metric aggregation, failure_gated, spec_drift, and CLI parsing.
7. Update verification notes after targeted and full test runs.

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

- [ ] The default fixture suite runs and returns stable aggregate metrics.
- [ ] JSON and Markdown render paths include all benchmark modes.

### Edge Cases

- [ ] failure_gated records false-close prevention for Sisyphus modes.
- [ ] spec_drift records drift detection for observation/evidence/trace modes.

### Exception Cases

- [ ] Missing or malformed benchmark fixtures fail with actionable errors.
- [ ] Unknown benchmark mode/scenario is rejected during fixture loading.

## Verification Mapping

- `Default fixture suite returns stable aggregate metrics` -> `tests.test_benchmark`
- `failure_gated/spec_drift behavior is captured` -> `tests.test_benchmark`
- `CLI parser accepts benchmark run surface` -> `tests.test_sisyphus`
- `Full repository behavior remains intact` -> `python -m unittest discover -s tests -v`

## External LLM Review

- Required: `no`
- Provider: `n/a`
- Purpose: `n/a`
- Trigger: `n/a`
