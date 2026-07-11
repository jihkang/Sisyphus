# Brief

## Task

- Task ID: `TF-20260614-feature-add-rl-ready-dataset-export`
- Type: `feature`
- Slug: `add-rl-ready-dataset-export`
- Branch: `feat/add-rl-ready-dataset-export`

## Problem

- Add RL-ready dataset export
- Original request: Add an RL-ready dataset export surface for Sisyphus harness episodes. Implement `sisyphus dataset export --format sft|rl [--task-id <id>] [--output <path>]` that reads existing task observations, episode traces, eval loop reward output, and test-first evaluation, then emits deterministic JSONL records for offline SFT/RL use. Do not implement live RL training in this task. The export must include failed and incomplete episodes when present, must not fabricate missing observations, and must align terminal reward fields with the existing eval/reward metrics.

## Desired Outcome

- The repository behavior matches the requested conversation outcome.
- The resulting change stays scoped to this task branch and worktree.

## Acceptance Criteria

- [x] `sisyphus dataset export --format sft|rl` emits deterministic JSONL.
- [x] `--task-id` scopes export to one task and default export includes repository-local tasks with episodes.
- [x] `--output` writes JSONL to a file; without `--output` the command writes JSONL to stdout.
- [x] SFT records contain messages with an observation payload and selected action payload.
- [x] RL records contain observation/action/result/terminal reward/metrics/test-first fields aligned with eval loop output.
- [x] Failed, incomplete, and missing-test-first episodes are included without fabricating observations.
- [x] Invalid format requests fail with an actionable parser error.

## Constraints

- Preserve existing repository conventions unless the task requires a deliberate change.
- Re-read the task docs before verify and close.
- Do not implement live RL training or online rollout collection in this task.
