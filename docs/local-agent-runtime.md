# Local Agent Runtime

The local agent is a policy adapter around an OpenAI-compatible chat endpoint. It is not a shell wrapper and does not grant the model Sisyphus lifecycle authority.

## Ownership

```text
task observation + frozen docs
            |
            v
provider_wrapper ---- unavailable ----> configured fallback provider
            |
            v
local coding policy <----HTTP----> local model server
            |
       one JSON action
            v
workspace executor --> scoped files / configured tests
            |
            +--> deterministic compact memory
            +--> local run receipt / episode trace
            +--> code-and-test completion gate
```

- `provider_wrapper.py` selects the effective provider, resolves the task worktree, builds the compact prompt, and independently checks completion.
- `providers/local_openai.py` owns endpoint configuration and OpenAI-compatible HTTP serialization.
- `providers/local_agent.py` owns the bounded turn loop, JSON action parsing, automatic compaction, and receipt.
- `providers/workspace.py` owns path containment, write scope, patch application, configured test execution, git inspection, and completion facts.
- Sisyphus planning, verification, closeout, and promotion retain lifecycle authority.

## Action Protocol

The model returns exactly one JSON object per turn. Supported actions are:

| Action | Effect |
| --- | --- |
| `list_files` | List tracked and unignored files with bounded output. |
| `read_file` | Read a UTF-8 line range. |
| `search` | Search literal text in bounded repository files. |
| `write_file` | Atomically replace one owned UTF-8 file. |
| `apply_patch` | Check and apply a unified git patch whose paths are all owned. |
| `git_diff` | Return bounded status and diff statistics. |
| `run_test` | Select an operator-configured command by numeric ID. |
| `finish` | Claim `completed`, `blocked`, or `failed`. |

Unknown actions are protocol errors. Text that resembles a command is never executed. Test commands are parsed with `shlex` and passed to `subprocess` with `shell=False`. The leading `python` or `python3` token resolves to the interpreter running the local worker, so the default test command stays inside the supported Sisyphus environment. Use an absolute executable path when a different interpreter is intentional.

## Workspace Boundary

Every file path is normalized and resolved against the task worktree. Mutation is rejected when a path:

- is absolute or contains `..`
- resolves outside the worktree through a symlink
- includes `.git` or `.planning`
- falls outside non-empty task `owned_paths`

Read and search actions may inspect repository code, but mutation is constrained by owned scope. Output, response, file, patch, and command limits bound resource usage.

## Automatic Compaction

The local policy estimates message tokens conservatively from serialized character count. Immutable task state remains in the base prompt. When dynamic history reaches the available budget, old assistant/tool turns are replaced by `COMPACTED_STATE` containing:

- event count
- changed files and completion readiness
- latest mutation and passing-test steps
- blocked action count
- bounded recent action results and errors

Compaction is deterministic and does not make a second model call. A receipt records `compaction_count`, so a harness can assert that a constrained-context run actually exercised compaction.

## Turn Sequence

```text
Sisyphus -> policy: compact observation, scope, action schema
policy -> model: messages within configured budget
model -> policy: one JSON action
policy -> executor: validated action
executor -> worktree: bounded read/write/patch/test
executor -> policy: bounded structured result
policy -> policy: compact old history when required
policy -> model: result or compact state and next turn
model -> policy: finish(completed)
policy -> executor: inspect diff and post-change test order
policy -> Sisyphus: accepted receipt or actionable failure
```

## Receipt Contract

`sisyphus.local_agent_run.v1` records:

- status, summary, and error
- source observation hash
- start and finish timestamps
- action, malformed-response, blocked-action, and compaction counts
- changed files and mutation/test ordering
- bounded action arguments and results

The wrapper persists this receipt under the task and projects each valid local action as `local_agent.<action>` into `sisyphus.episode_trace.v1`. Existing eval and dataset paths can therefore count and inspect local-model actions without trusting the model's summary.

## Effectiveness Claim

A successful real-model fixture proves only that the tested model, quantization, prompt, action limits, and repository fixture can complete that small task class. It does not establish general coding competence. Keep the model version, server version, receipt, diff, test output, compaction count, blocked action count, and wall-clock duration with any reported result.
