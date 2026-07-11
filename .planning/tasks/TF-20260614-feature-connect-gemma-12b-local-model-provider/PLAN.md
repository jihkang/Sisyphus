# Plan

## Implementation Plan

1. Inspect `src/sisyphus/agent_runtime.py`, provider launch paths, MCP action boundaries, and current Codex wrapper behavior.
2. Define a provider config shape for local Gemma 12B:
   - model alias
   - local server URL or launch command
   - context/window limits
   - timeout and stop-token settings
   - observation/action prompt template
3. Prefer an OpenAI-compatible local server contract first so llama.cpp, Ollama, LM Studio, or other local runtimes can be used behind one adapter.
4. Add a local provider adapter that receives `task://<task-id>/observation`-derived context and returns structured action proposals.
5. Add CLI or config wiring so an operator can select the local Gemma provider for a Sisyphus worker.
6. Add tests with a fake local server/client so CI does not require model downloads.
7. Document operator setup in `docs/local-models.md`.

## Risks

- Local model runtimes differ; keep the first adapter narrow and OpenAI-compatible where possible.
- Gemma 12B may exceed available local memory; configuration must be operator-provided.
- A local provider must not bypass Sisyphus lifecycle/action boundaries.
- CI cannot assume model weights are present.

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

- [ ] Local provider config is parsed and validated.
- [ ] Existing local server mode can produce a structured action proposal from a task observation.
- [ ] Sisyphus worker flow can select the local Gemma provider without changing task lifecycle rules.

### Edge Cases

- [ ] Missing model/server configuration fails with an actionable error.
- [ ] Fake local provider test runs without model weights.

### Exception Cases

- [ ] Provider timeout/server failure is recorded without mutating task state incorrectly.
- [ ] Review-gated actions remain forbidden to the local policy unless explicitly operator-driven.

## Verification Mapping

- `Local provider config and fake server flow` -> `targeted unit tests`
- `Lifecycle/action boundary preservation` -> `existing lifecycle/action tests plus local provider tests`
- `Operator setup documentation` -> `docs/local-models.md review`
- `Full repository behavior remains intact` -> `python -m unittest discover -s tests -v`

## External LLM Review

- Required: `no`
- Provider: `n/a`
- Purpose: `n/a`
- Trigger: `n/a`
