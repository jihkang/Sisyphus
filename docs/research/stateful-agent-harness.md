# Stateful Agent Harness

Sisyphus is a repository-local control plane for AI-assisted software work. Its core design goal is to keep bookkeeping outside the model.

The harness owns task state, lifecycle validity, conformance, evidence, verification, promotion, and closeout. A worker or policy reads compact state, selects an action through a bounded interface, and lets Sisyphus validate the transition.

```text
state_t
-> observation_t
-> action_t
-> transition
-> state_t+1
```

## Implemented Runtime Pieces

- Observation renderer: `src/sisyphus/observation.py`
- Lifecycle rules: `src/sisyphus/lifecycle_rules.py`
- Action registry: `src/sisyphus/action_space.py`
- Episode trace: `src/sisyphus/episode_trace.py`
- Evidence graph: `src/sisyphus/evidence_graph.py`
- Reward and eval loop: `src/sisyphus/reward.py`, `src/sisyphus/eval/loop.py`
- Test-first loop check: `src/sisyphus/test_first.py`
- Benchmark fixtures: `src/sisyphus/benchmark.py`, `benchmarks/tasks/harness-fixtures.json`
- Dataset export: `src/sisyphus/dataset_export.py`

## Agent-Facing Observation

Agents should read `task://<task-id>/observation` or run:

```bash
sisyphus observe <task-id> --json
```

The observation includes lifecycle status, plan/spec status, verification summary, conformance summary, gates, required docs, subtasks, evidence summary, promotion state, allowed actions, forbidden actions, and a stable observation hash.

The observation is the canonical compact state for execution decisions. Chat history is not.

## Action Boundary

Sisyphus separates policy-safe actions from judgment-gated actions. A policy may safely perform read-only actions and low-risk writes such as verification or plan revision when lifecycle rules allow them. Human judgment remains required for plan approval, spec freeze, close, promotion execution, and merged-PR receipt recording.

This keeps automation aggressive around mechanical work while keeping irreversible or judgment-heavy transitions conservative.

## Evaluation Boundary

Sisyphus currently supports offline evaluation and dataset export, not online RL training. The implemented path is:

```text
observation + episode trace + evidence + task outcome
-> eval loop
-> reward metrics
-> SFT/RL JSONL export
```

Live trainer integration should be added only after enough real traces exist and after local-provider execution boundaries are stable.

## Local Model Follow-Up

The linked runtime integration task is:

- `TF-20260614-feature-connect-gemma-12b-local-model-provider`

That task should connect a local Gemma 12B runtime to Sisyphus' observation/action/eval loop without changing the judgment boundary.
