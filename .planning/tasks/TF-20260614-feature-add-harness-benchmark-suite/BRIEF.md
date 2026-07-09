# Brief

## Task

- Task ID: `TF-20260614-feature-add-harness-benchmark-suite`
- Type: `feature`
- Slug: `add-harness-benchmark-suite`
- Branch: `feat/add-harness-benchmark-suite`

## Problem

- Add harness benchmark and ablation suite
- Original request: Add a small benchmark suite that measures whether Sisyphus harness features improve verified software-work completion.

Scope:
- Add `benchmarks/` with deterministic fixture task definitions for bugfix_basic, feature_small, refactor_safe, docs_sync, failure_gated, spec_drift, and promotion_ready.
- Define modes: plain agent fixture, Sisyphus basic, Sisyphus with observation, Sisyphus with observation plus evidence, and Sisyphus with trace/replay.
- Implement a deterministic benchmark evaluator that can run without a live LLM, without mutating real task state, and without cloning external repos.
- Track metrics: task_success_rate, verify_pass_rate, close_success_rate, false_close_rate, conformance_green_rate, spec_drift_detected_rate, evidence_completeness, action_count, unrelated_diff_ratio, reproducibility_score, and human_intervention_count.
- Add CLI output for JSON and concise Markdown.

Acceptance criteria:
- Benchmark runner can execute the fixture set locally.
- failure_gated proves close is blocked when verification fails.
- spec_drift proves conformance yellow/red is detected before close.
- Results render as JSON and concise markdown.
- The runner is deterministic and has no provider/model dependency.

Dependency: should follow eval loop runner; can start with deterministic fixtures before any live agent mode.

## Desired Outcome

- The repository behavior matches the requested conversation outcome.
- The resulting change stays scoped to this task branch and worktree.

## Acceptance Criteria

- [ ] Benchmark fixtures cover the seven requested scenarios.
- [ ] Benchmark modes cover the five requested harness modes.
- [ ] Metrics are stable and machine-readable.
- [ ] JSON and Markdown render paths are tested.
- [ ] Verification notes are ready to be updated after implementation.

## Constraints

- Preserve existing repository conventions unless the task requires a deliberate change.
- Re-read the task docs before verify and close.
