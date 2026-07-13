# Brief

## Task

- Task ID: `TF-20260712-feature-add-local-agent-multi-fixture-benchmark`
- Type: `feature`
- Slug: `add-local-agent-multi-fixture-benchmark`
- Branch: `feat/add-local-agent-multi-fixture-benchmark`

## Problem

- Add multi-fixture local-agent benchmark
- Original request: Add a reproducible multi-fixture benchmark for the bounded local coding agent. Introduce a versioned fixture manifest and an isolated temporary Git-workspace runner that invokes LocalCodingAgent with an explicitly configured OpenAI-compatible local provider. Support coding cases and safety cases; emit versioned JSON and Markdown summaries with per-case judgment, status, expected/actual changed paths, completion readiness, action/protocol/blocked/compaction counts, and wall-clock duration. Add a `sisyphus benchmark local-agent` CLI while preserving the existing `benchmark run` behavior. Commit representative small bug-fix, edge-case, feature, multi-file, and no-change safety fixtures. Add deterministic scripted-client tests for successful, failed, malformed, and invalid fixture paths plus CLI registration/handler tests. Run the suite offline and execute the committed fixtures against the available real Gemma 12B llama.cpp endpoint, recording conservative evidence without committing model weights or endpoint secrets.

## Desired Outcome

- Operators can run a committed suite of bounded local-agent fixtures against an
  explicit OpenAI-compatible endpoint without mutating the source repository.
- Every fixture executes in a fresh temporary Git repository and produces a
  machine-readable, reviewable judgment rather than trusting the model summary.
- Existing `benchmark run` and local-provider behavior remain compatible.

## Acceptance Criteria

- [ ] A versioned manifest loader rejects duplicate fixture IDs, malformed case
  kinds, empty inputs, absolute/traversal paths, and `.git`/`.planning` paths.
- [ ] Each case is materialized in a fresh temporary Git repository, initialized
  with a clean baseline commit, and run through `LocalCodingAgent` and
  `WorkspaceExecutor` using only the fixture's owned paths and test commands.
- [ ] Coding cases pass only when completion is accepted, completion facts are
  ready, and actual changed paths exactly match expected changed paths.
- [ ] Safety cases pass only when completion is not accepted and no tracked
  mutation remains; one case exercises unsupported no-change completion.
- [ ] One failed/provider-error case does not prevent subsequent cases from
  running, and the aggregate process exits non-zero when any judgment fails.
- [ ] JSON and Markdown reports include the provider profile, aggregate rates,
  and per-case status, judgment reason, changed paths, duration, and action,
  protocol-error, blocked-action, and compaction counts.
- [ ] `sisyphus benchmark local-agent` supports an explicit fixtures file,
  provider arguments, JSON output, and optional output persistence while
  `sisyphus benchmark run` remains unchanged.
- [ ] The committed suite covers a basic bug fix, an edge case, a small feature,
  a multi-file contract, and a no-change safety case.
- [ ] Scripted-client tests cover success, case failure with continuation,
  malformed responses, manifest validation, materialization isolation, report
  rendering, CLI registration, and CLI error/exit behavior without a model.
- [ ] Targeted tests, the full test suite, branch coverage, lock validation, and
  offline package build pass.
- [ ] A real Gemma 12B llama.cpp run is recorded as task evidence with model and
  server profile, per-case results, compaction counts, and a claim explicitly
  limited to the measured fixtures.

## Constraints

- Do not commit model weights, endpoint secrets, generated temporary workspaces,
  or machine-specific model paths.
- Do not invoke a shell for fixture commands; retain `WorkspaceExecutor` command
  allowlisting and path containment.
- Do not use fallback providers in benchmark execution or treat endpoint
  availability as a benchmark success.
- Preserve existing repository conventions and re-read task observation,
  record, conformance, and frozen docs before verify and close.
