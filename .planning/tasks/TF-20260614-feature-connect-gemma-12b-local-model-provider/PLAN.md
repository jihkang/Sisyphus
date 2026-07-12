# Plan

## Implementation Plan

1. Preserve the latest-main baseline.
   - Run the full unit suite and the existing seven-scenario harness benchmark before implementation.
   - Record the baseline test count and benchmark modes for post-change comparison.

2. Add the local OpenAI-compatible provider boundary.
   - Parse machine-neutral endpoint, model, timeout, generation, context, action-budget, test-command, and fallback settings.
   - Probe the existing server through `/v1/models`; fall back only when explicitly configured.
   - Keep HTTP serialization and response extraction separate from workspace mutation.

3. Build a bounded local coding loop.
   - Send a compact task observation, frozen scope, execution contract, and action schema to the model.
   - Accept exactly one JSON action per turn from a fixed registry: list, read, search, write, patch, diff, test, or finish.
   - Reject malformed or unknown actions with bounded retries and never interpret model text as a shell command.

4. Add a worktree-scoped executor.
   - Resolve every path against the assigned task worktree and reject traversal, symlink escape, `.git`, `.planning`, and out-of-scope writes.
   - Execute only operator-configured test commands with `shell=False`, timeout, and bounded output.
   - Track mutations, changed paths, successful test ordering, blocked actions, and code-level result status.

5. Add automatic context compaction.
   - Estimate prompt usage conservatively from serialized message size.
   - When dynamic history reaches the configured budget, replace old turns with deterministic structured memory containing changed files, test outcomes, recent errors, and bounded relevant excerpts.
   - Preserve the immutable task observation and record compaction events and counts in the run receipt.

6. Integrate with the existing provider wrapper and Sisyphus evidence flow.
   - Select the local worker for `gemma`, `local-openai`, and `llama-server` aliases while preserving Codex behavior and effective-provider attribution on fallback.
   - Pass the resolved task worktree and owned paths to the local worker.
   - Reject a `completed` claim unless non-planning changes and a post-mutation passing test are independently observable.
   - Project local actions into a task-local episode trace or receipt suitable for the existing eval loop without granting lifecycle authority.

7. Verify with fake and real providers.
   - Add deterministic fake-server unit and integration tests for configuration, protocol parsing, security, compaction, fallback, failure, and completion.
   - Start `llama-server` with the operator-managed Gemma 12B GGUF and run an isolated coding fixture through the Sisyphus task/provider path.
   - Require a scoped code diff, post-change passing test, successful receipt, at least one forced compaction, and zero blocked tool attempts before declaring the architecture effective for the tested task class.

8. Document and promote.
   - Document llama.cpp setup, provider arguments, action boundaries, completion semantics, and the limits of the measured result.
   - Run targeted tests, full regression, branch coverage, package build, Sisyphus verify, PR CI, and merge-receipt closeout.

## Risks

- A 12B model may emit malformed JSON or weak patches. Mitigation: strict parsing, bounded correction turns, small action schema, clear tool results, and an isolated fixture before broader claims.
- Model-controlled arbitrary commands would create a code-execution boundary. Mitigation: the model selects only an index into operator-configured test commands and subprocesses run without a shell.
- Path traversal or symlink escape could mutate files outside the worktree. Mitigation: resolved-path containment checks, protected path rejection, and owned-scope enforcement on every mutation.
- Compacting too aggressively can discard information needed for a correct edit. Mitigation: retain immutable task state plus deterministic changed-file, test, error, and recent-excerpt memory and test forced compaction explicitly.
- A text-only completion can look successful without code. Mitigation: require a non-planning diff and a passing test after the latest mutation in both the local loop and wrapper finalizer.
- Provider integration could regress Codex execution. Mitigation: retain the existing launch path and add regression tests for command, prompt, status, and fallback attribution.
- One fixture cannot establish general coding competence. Mitigation: report the result as evidence for the small-feature task class, include action/compaction/test metrics, and avoid broader claims.

## Design Evaluation

- Design Mode: `full`
- Decision Reason: `introduces a local-model provider contract, a bounded code-action runtime, and an automatic context-compaction boundary`
- Confidence: `medium`
- Layer Impact: `layer-adding`
- Layer Decision Reason: `adds provider, workspace-tool, and local-agent orchestration responsibilities used by the shared provider wrapper`
- Required Design Artifacts: `connection_diagram, sequence_diagram, boundary_note`

## Design Artifacts

- Connection Diagram: `the connection diagram below defines provider, policy, executor, and evidence ownership`
- Sequence Diagram: `the sequence diagram below defines one bounded model/tool turn and completion acceptance`
- Boundary Note: `the model proposes JSON actions only; Sisyphus validates paths and commands, mutates the worktree, records receipts, and retains all lifecycle judgment`

### Connection Diagram Details

```text
task observation + frozen docs
            |
            v
provider_wrapper ---- unavailable ----> configured fallback provider
            |
            v
local coding policy <----HTTP----> OpenAI-compatible Gemma 12B server
            |
       JSON action
            v
workspace executor --> scoped files / operator test commands
            |
            +--> deterministic compact memory
            +--> local run receipt / episode evidence
            +--> code-and-test completion gate
```

### Sequence Diagram Details

```text
Sisyphus -> local policy: compact observation, scope, action schema
local policy -> Gemma: messages within configured context budget
Gemma -> local policy: one JSON action
local policy -> executor: validated action
executor -> worktree: bounded read/write/patch/test
executor -> local policy: bounded structured result
local policy -> local policy: compact old history when threshold is reached
local policy -> Gemma: result or compact memory and next turn
Gemma -> local policy: finish(completed)
local policy -> executor: inspect non-planning diff and post-change test order
local policy -> Sisyphus: completed receipt or actionable failure
```

## Test Strategy

### Normal Cases

- [x] Local provider configuration and health probing select the requested endpoint and model
- [x] A fake model reads a fixture, writes an in-scope implementation, reruns its configured test, and completes with a receipt
- [x] Existing Codex launch behavior remains unchanged and unavailable Gemma uses only the configured fallback
- [x] A real Gemma 12B Sisyphus fixture produces a scoped code change and a post-change passing test

### Edge Cases

- [x] Forced low history budget triggers deterministic compaction while retaining changed-file and test state
- [x] A `.planning`-only change does not satisfy the code-level completion gate
- [x] Read output, search results, model responses, and test output are truncated without changing control flow
- [x] A model retry after malformed JSON remains within the action and protocol-error budgets

### Exception Cases

- [x] Path traversal, symlink escape, protected path writes, and out-of-owned-scope writes are rejected without filesystem mutation
- [x] Unknown actions and arbitrary command text are rejected rather than executed
- [x] Endpoint timeout, invalid response JSON, and exhausted action budget fail with actionable receipts
- [x] `completed` without a non-planning diff or without a passing test after the latest mutation is rejected
- [x] Blocked or failed model finish status marks the tracked agent failed and cannot advance lifecycle state

## Verification Mapping

- `Local provider configuration and health probing select the requested endpoint and model` -> `tests/test_local_provider.py configuration and fake HTTP tests`
- `A fake model reads a fixture, writes an in-scope implementation, reruns its configured test, and completes with a receipt` -> `tests/test_local_provider.py bounded-loop integration test`
- `Existing Codex launch behavior remains unchanged and unavailable Gemma uses only the configured fallback` -> `tests/test_sisyphus.py provider-wrapper regression tests`
- `A real Gemma 12B Sisyphus fixture produces a scoped code change and a post-change passing test` -> `operator-managed llama-server E2E receipt plus fixture git diff and unittest output`
- `Forced low history budget triggers deterministic compaction while retaining changed-file and test state` -> `tests/test_local_provider.py compaction test and real E2E receipt compaction_count assertion`
- `A .planning-only change does not satisfy the code-level completion gate` -> `tests/test_local_provider.py completion-gate test`
- `Read output, search results, model responses, and test output are truncated without changing control flow` -> `tests/test_local_provider.py output-boundary tests`
- `A model retry after malformed JSON remains within the action and protocol-error budgets` -> `tests/test_local_provider.py malformed-response recovery test`
- `Path traversal, symlink escape, protected path writes, and out-of-owned-scope writes are rejected without filesystem mutation` -> `tests/test_local_provider.py workspace security tests`
- `Unknown actions and arbitrary command text are rejected rather than executed` -> `tests/test_local_provider.py action-registry tests`
- `Endpoint timeout, invalid response JSON, and exhausted action budget fail with actionable receipts` -> `tests/test_local_provider.py provider failure tests`
- `completed without a non-planning diff or without a passing test after the latest mutation is rejected` -> `tests/test_local_provider.py ordered completion-gate tests`
- `Blocked or failed model finish status marks the tracked agent failed and cannot advance lifecycle state` -> `tests/test_sisyphus.py tracked-provider finalization tests`
- `Full repository behavior remains intact` -> `python -m unittest discover -s tests`
- `Coverage and package metadata remain valid` -> `coverage run --branch -m unittest discover -s tests && coverage report --fail-under=80` and `uv build --no-sources --offline --clear`

## External LLM Review

- Required: `no`
- Provider: `not applicable; Gemma 12B is the system under test`
- Purpose: `the real-model run is deterministic verification evidence for the bounded runtime, not an independent review opinion`
- Trigger: `use an independent reviewer only if claims expand beyond the measured fixture`

## Out Of Scope

- Downloading, converting, fine-tuning, or redistributing model weights.
- Online RL training or autonomous promotion and closeout.
- General-purpose shell access, network browsing, package installation, or unrestricted tool calling by the model.
- Claims of general coding-agent superiority beyond the measured isolated fixture and recorded limits.
