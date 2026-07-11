# Dataset Export

Dataset export turns recorded Sisyphus episodes into offline SFT or RL JSONL records.

Implementation:

- `src/sisyphus/dataset_export.py`

CLI:

```bash
sisyphus dataset export --format sft --task-id <task-id>
sisyphus dataset export --format rl --output artifacts/rollouts.jsonl
```

## Formats

`sft` records contain:

- system message
- user message with observation hash and state-before payload
- assistant message with selected action and arguments
- result
- terminal status
- reward payload
- test-first payload

`rl` records contain:

- observation payload
- action
- result
- transition state and diff
- terminal status
- reward
- metrics
- test-first payload

## Determinism

Records are emitted as sorted-key JSONL. Default export includes tasks that have recorded episode steps. `--task-id` scopes export to one task.

Missing episode traces produce no fabricated records. Failed and incomplete episodes remain exportable when traces exist.

## Boundary

This is an offline data export path. It does not train a model, launch rollouts, or modify task state.
