# Episode Trace

Episode traces record what the agent saw, which action was selected, what result came back, and how task state changed.

Implementation:

- `src/sisyphus/episode_trace.py`
- MCP trace wiring in `src/sisyphus/mcp_core.py`

Default path:

```text
.planning/tasks/<task-id>/artifacts/episodes/<episode-id>.jsonl
```

## Step Shape

Each step stores:

- schema version
- episode id
- task id
- step number
- timestamp
- `task://<task-id>/observation` state ref
- observation hash
- actor metadata
- action name and arguments
- tool result
- state before
- state after
- state diff

Do not store chain-of-thought in episode traces. Store observation, selected action, arguments, results, state diffs, gates, and evidence references.

## CLI

Use:

```bash
sisyphus episode check <task-id> --json
```

This validates basic trace shape, increasing step order, task binding, and action summaries.

## Why It Matters

Episode traces support:

- failure replay and audit
- provider comparison
- reward/eval calculation
- SFT/RL dataset export
- discovery vs curation analysis
