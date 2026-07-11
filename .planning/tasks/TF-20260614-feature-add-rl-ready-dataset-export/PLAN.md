# Plan

## Implementation Plan

1. Inspect episode trace, eval loop, reward, observation, and CLI parser surfaces.
2. Add `dataset_export.py` with deterministic task discovery and JSONL record builders.
3. Define two export formats:
   - `sft`: message records with system, observation, and action JSON payloads.
   - `rl`: transition records with observation hash, action, result, terminal reward, metrics, terminal status, and test-first evaluation.
4. Include only recorded episode steps for training records; do not fabricate missing step observations.
5. Include failed/incomplete episodes and expose their result/reward fields rather than filtering them out.
6. Add `sisyphus dataset export --format sft|rl [--task-id <id>] [--output <path>]`.
7. Add tests for SFT export, RL export, task scoping, stdout/file output shape, and parser validation.

## Risks

- Exporting all tasks could accidentally include tasks without episode traces; keep default deterministic and episode-backed.
- Reward totals must stay aligned with `eval.loop` rather than introducing a second scoring implementation.
- SFT records must remain action-supervision examples, not hidden reasoning traces.

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

- [x] SFT export emits stable message JSONL for recorded actions.
- [x] RL export emits reward-aligned transition JSONL for recorded actions.
- [x] CLI writes export records to stdout or `--output`.

### Edge Cases

- [x] Task scoping exports only the requested task.
- [x] Missing episode traces produce no fabricated records.
- [x] `not_recorded`/`incomplete` test-first status is preserved in exported metadata.

### Exception Cases

- [x] Unsupported export formats are rejected by the parser.
- [x] Missing task IDs fail with the existing task loading error.

## Verification Mapping

- `SFT/RL export shape and reward alignment` -> `tests.test_dataset_export`
- `CLI parser accepts dataset export surface` -> `tests.test_sisyphus`
- `Full repository behavior remains intact` -> `python -m unittest discover -s tests -v`

## External LLM Review

- Required: `no`
- Provider: `n/a`
- Purpose: `n/a`
- Trigger: `n/a`
