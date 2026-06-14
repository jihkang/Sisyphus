# Plan

## Implementation Plan

1. Inspect the current reward, metrics, evolution fitness, evidence graph, episode trace, observation, and CLI surfaces.
2. Add a small read-only eval package that derives task outcome facts from task state plus optional evidence and episode artifacts.
3. Extend reward scoring so eval metrics and reward components use the same stable names.
4. Add a loop result API and CLI command that renders the offline shape: observation_t -> recorded actions/results -> observation_t+1 -> reward/outcome.
5. Expose a test-first loop TODO/phase in the eval result so later work can require test generation before implementation.
6. Add regression tests for passing, failed verification, conformance yellow/red, missing evidence, excessive actions, and CLI parsing.
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

- [ ] Closed, verified, green task with complete evidence scores positively.
- [ ] Eval loop output contains stable metric names aligned with reward fields.

### Edge Cases

- [ ] Missing evidence is visible even when task state is otherwise verified.
- [ ] Excessive recorded episode actions are counted and penalized.

### Exception Cases

- [ ] False close and conformance yellow/red produce explicit penalty facts.
- [ ] Missing episode files are tolerated as zero recorded actions.

## Verification Mapping

- `Closed verified task scores positively` -> `tests.test_eval_loop`
- `False close/conformance/missing evidence penalties are explicit` -> `tests.test_eval_loop` and `tests.test_reward`
- `CLI surface parses eval loop command` -> `tests.test_sisyphus`
- `Full repository behavior remains intact` -> `python -m unittest discover -s tests -v`

## External LLM Review

- Required: `no`
- Provider: `n/a`
- Purpose: `n/a`
- Trigger: `n/a`
