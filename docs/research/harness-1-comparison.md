# Harness-1 Comparison

Harness-1 is useful as an analogy because it emphasizes a structured environment loop rather than transcript-only agent execution. Sisyphus applies the same systems idea to software workflow tasks.

## Similar Shape

Both systems benefit from the same control structure:

```text
state_t -> observation_t -> action_t -> transition -> state_t+1
```

For Sisyphus:

- `state_t`: repository-local task record, docs, gates, conformance, evidence, promotion state, and artifacts
- `observation_t`: `task://<task-id>/observation` or `sisyphus observe <task-id> --json`
- `action_t`: named Sisyphus CLI/MCP action from the action registry
- `transition`: lifecycle/evidence/conformance validation plus state mutation when allowed
- `state_t+1`: updated task state, episode trace, evidence graph, verify output, or promotion receipt

## Key Difference

Harness-1 is commonly discussed around retrieval and training loops. Sisyphus is first a verification-centered software-work harness. Its primary safety question is not "did the model retrieve the answer?" but "did the work complete correctly, with evidence, without violating lifecycle gates?"

## Sisyphus Evaluation Axes

Sisyphus should be evaluated on verified work completion:

- task success rate
- verify pass rate
- false close rate
- conformance green rate
- spec drift detection
- evidence completeness
- action count
- time to verify
- unrelated diff ratio
- reproducibility score
- human intervention count

These map to implemented or emerging surfaces in `src/sisyphus/reward.py`, `src/sisyphus/eval/loop.py`, `src/sisyphus/benchmark.py`, and `src/sisyphus/dataset_export.py`.

## Discovery vs Curation

Sisyphus can separate two failure modes:

- trajectory discovery: the agent encountered the needed file, test failure, spec section, conformance warning, or evidence
- curated completion: the final verify, changeset, and evidence graph preserved that information correctly

This distinction is what makes episode traces and curated evidence useful beyond ordinary task logging.

## Current Boundary

Sisyphus is RL-ready in the environment-interface sense: observations, actions, rewards, traces, benchmark fixtures, and dataset export now exist. It is not yet an online RL trainer. PPO/GRPO-style training should remain out of scope until local provider execution, replay, and dataset quality are stronger.
