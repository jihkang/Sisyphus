# Reward Model

Sisyphus reward scoring is implemented in `src/sisyphus/reward.py` and projected through `src/sisyphus/eval/loop.py`.

The reward model is an offline evaluator for recorded task outcomes. It is not an online trainer.

## Positive Components

Current reward metrics include:

- `task_closed`
- `verify_passed`
- `conformance_green`
- `promotion_complete`
- `evidence_complete`
- `gates_clear`
- `no_false_close`
- `action_efficiency`
- `reward_total`

The metric names are exported as `REWARD_METRIC_NAMES`.

## Penalties

Current penalties include:

- `false_close`
- `conformance_red`
- `conformance_not_green_at_close`
- `promotion_missing_at_close`
- `blocking_gates_at_close`
- `missing_evidence`
- `unsupported_evidence`
- `excessive_action_count`

## Eval Loop

Use:

```bash
sisyphus eval loop <task-id> --json
```

The result includes observation hashes, episode counts, action summaries, terminal status, outcome facts, reward components, penalties, metrics, and test-first status.

## Dataset Export

Use:

```bash
sisyphus dataset export --format rl --task-id <task-id>
```

RL records reuse the eval loop reward payload. There is no separate reward implementation in the dataset exporter.
