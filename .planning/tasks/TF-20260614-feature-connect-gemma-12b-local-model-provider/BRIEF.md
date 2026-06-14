# Brief

## Task

- Task ID: `TF-20260614-feature-connect-gemma-12b-local-model-provider`
- Type: `feature`
- Slug: `connect-gemma-12b-local-model-provider`
- Branch: `feat/connect-gemma-12b-local-model-provider`

## Problem

- Connect Gemma 12B local model provider
- Original request: Add a linked follow-up task for applying Sisyphus directly when opening a local model, with Gemma 12B as the initial local provider target. The task should define how Sisyphus launches or connects to a local Gemma 12B runtime, exposes it through the provider/runtime abstraction, and lets Sisyphus observation/action/eval flow apply immediately to local-model workers. Do not implement this in the documentation task; keep it as a separate runtime integration task.

## Desired Outcome

- The repository behavior matches the requested conversation outcome.
- The resulting change stays scoped to this task branch and worktree.

## Acceptance Criteria

- [ ] Define a local provider configuration for Gemma 12B without hardcoding a machine-specific model path.
- [ ] Support connecting to an existing local OpenAI-compatible server or launching a configured local runtime.
- [ ] Project Sisyphus task observation into the local provider prompt/input path.
- [ ] Preserve action-space and lifecycle boundaries when the worker is local-model backed.
- [ ] Add a smoke path that can run without downloading a model in CI.
- [ ] Document required operator setup for model weights/runtime outside repository state.

## Constraints

- Preserve existing repository conventions unless the task requires a deliberate change.
- Re-read the task docs before verify and close.
- Do not download model weights into the repository.
- Do not add online RL training in this task.
- Keep approval, freeze, close, and promotion judgment-gated.
