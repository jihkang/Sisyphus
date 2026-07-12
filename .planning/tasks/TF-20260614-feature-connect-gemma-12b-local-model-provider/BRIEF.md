# Brief

## Task

- Task ID: `TF-20260614-feature-connect-gemma-12b-local-model-provider`
- Type: `feature`
- Slug: `connect-gemma-12b-local-model-provider`
- Branch: `feat/connect-gemma-12b-local-model-provider`

## Problem

- Sisyphus can track an external provider process, but the default worker path only launches Codex.
- The earlier local Gemma experiment could obtain a text response from an OpenAI-compatible endpoint, but it had no bounded code tools. The model reported `STATUS: completed` while producing no repository change.
- Long local-agent histories are not compacted, so an 8K-class local context window cannot sustain a multi-step inspect, edit, and test loop.

## Desired Outcome

- An operator can select a Gemma 12B or generic OpenAI-compatible local endpoint as a Sisyphus worker without storing model weights or machine-specific paths in the repository.
- The local model receives the canonical task observation and proposes one structured action at a time; Sisyphus owns path validation, file mutation, test execution, lifecycle boundaries, and completion acceptance.
- The worker compacts accumulated tool history automatically and persists a reproducible receipt.
- A real Gemma 12B run can complete a small isolated coding fixture with a scoped code change and a post-change passing test.

## Acceptance Criteria

- [x] Local provider configuration supports an operator-supplied OpenAI-compatible base URL, model alias, limits, test commands, and optional fallback without a hardcoded model path.
- [x] Provider prompts include `task://<task-id>/observation` state and frozen task scope in a context-bounded form.
- [x] The local coding loop accepts only a documented JSON action protocol and enforces a finite action budget.
- [x] Read, search, write, patch, diff, and test tools remain inside the assigned task worktree; writes to `.git`, `.planning`, path traversal targets, and paths outside owned scope are rejected.
- [x] Automatic compaction replaces old tool history with deterministic structured memory before the configured context budget is exceeded and records the compaction count.
- [x] A local `completed` claim is accepted only when a non-planning repository change exists and a configured test passed after the latest mutation.
- [x] Provider failure, malformed output, blocked status, exhausted budget, and unavailable endpoint produce actionable failure state without bypassing Sisyphus lifecycle gates.
- [x] Fake-server tests cover the provider, action loop, security boundaries, compaction, fallback, and completion gate without requiring model weights in CI.
- [x] A real Gemma 12B fixture run produces an in-scope code change, passes its test, records at least one compaction under a constrained test budget, and reports no blocked tool attempt.
- [x] Operator setup and the runtime/action/compaction contract are documented without committing model weights or local absolute paths as defaults.

## Constraints

- Do not download or commit model weights, generated model output, secrets, or machine-specific model paths.
- Do not expose arbitrary shell execution chosen by the model; only operator-configured test commands may run.
- Do not let the local policy approve plans, freeze specs, close tasks, execute promotion, or record merged PRs.
- Preserve Codex provider behavior and the existing provider wrapper interface.
- Keep online RL training out of scope; this task may emit receipts and episode evidence for existing offline evaluation.
