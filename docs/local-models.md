# Local Model Providers

Sisyphus can use a Gemma model or another OpenAI-compatible local endpoint as a bounded coding worker. The model proposes JSON actions; Sisyphus validates and executes those actions inside the task worktree.

## Requirements

- A local OpenAI-compatible server such as `llama-server`
- Model weights managed outside the repository
- A reviewed Sisyphus task with an approved plan and frozen spec
- At least one operator-configured test command

The repository does not download, locate, or redistribute model weights.

## llama-server

Set the model location only in the operator environment:

```bash
export GEMMA_GGUF=/absolute/path/to/gemma-12b.gguf

llama-server \
  --model "$GEMMA_GGUF" \
  --host 127.0.0.1 \
  --port 8080 \
  --ctx-size 8192 \
  --parallel 1 \
  --alias gemma-12b \
  --no-ui
```

Do not enable `llama-server --tools`. Sisyphus supplies a smaller workspace tool set and enforces its own path, command, and completion checks.

Check the endpoint before assigning work:

```bash
curl http://127.0.0.1:8080/v1/models
```

## Configuration

The `gemma` alias defaults to:

- Base URL: `http://127.0.0.1:8080/v1`
- Model alias: `gemma-12b`
- Fallback provider: `codex`
- Context window: `8192` tokens
- Maximum actions: `24`
- Test command: `python3 -m unittest discover -s tests`

Environment variables provide persistent operator-level endpoint settings:

```bash
export SISYPHUS_GEMMA_BASE_URL=http://127.0.0.1:8080/v1
export SISYPHUS_GEMMA_MODEL=gemma-12b
export SISYPHUS_LOCAL_MODEL_FALLBACK_PROVIDER=codex
```

Generic aliases also use `SISYPHUS_LOCAL_MODEL_BASE_URL` and `SISYPHUS_LOCAL_MODEL_NAME`. An API key can be supplied through `SISYPHUS_LOCAL_MODEL_API_KEY`.

Provider arguments configure an explicit worker invocation:

```bash
--provider-arg=--base-url \
--provider-arg=http://127.0.0.1:8080/v1 \
--provider-arg=--model \
--provider-arg=gemma-12b \
--provider-arg=--max-steps \
--provider-arg=20 \
--provider-arg=--context-window \
--provider-arg=8192 \
--provider-arg=--test-command \
--provider-arg="python -m unittest discover -s tests"
```

Use `--provider-arg=--no-fallback` when endpoint failure must fail the run instead of selecting Codex.

## Task Flow

Create the task with the local provider and explicit write scope:

```bash
sisyphus request "Implement the reviewed small feature" \
  --provider gemma \
  --owned-path src/example \
  --owned-path tests
```

New tasks still stop for plan approval and spec freeze. After those judgment gates, a workflow cycle reads `meta.default_provider` and launches the bounded local worker:

```bash
sisyphus daemon --once
```

For controlled evaluation, call `run_provider_wrapper("gemma", ...)` with explicit provider arguments after the same plan and spec gates have cleared.

## Completion

`STATUS: completed` is only a claim. Sisyphus accepts it when all of the following are true:

1. The current run performed a permitted write or patch.
2. Git reports a changed path outside `.planning`.
3. A configured test passed after the latest mutation.
4. The structured receipt reports the same changed file and test order.
5. The wrapper independently observes the receipt and worktree diff.

A failed condition marks the tracked agent failed with an `unsupported completion claim` error. Plan approval, spec freeze, verification, close, and promotion remain separate Sisyphus gates.

## Evidence

Successful and failed local runs write:

- `artifacts/local-agent/<agent-id>.json`: provider action and compaction receipt
- `artifacts/episodes/ep-<task-id>-<agent-id>.jsonl`: actions projected into the existing episode schema

Run the existing evaluators against the projected episode:

```bash
sisyphus episode check <task-id> --json
sisyphus eval loop <task-id> --episode-id ep-<task-id>-<agent-id> --json
```

See [Local Agent Runtime](local-agent-runtime.md) for the action, compaction, and trust boundaries.
