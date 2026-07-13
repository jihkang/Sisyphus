# Plan

## Implementation Plan

1. Define immutable fixture and result models in a provider-owned benchmark
   module. Parse a versioned JSON manifest with strict type, ID, path, case-kind,
   owned-scope, test-command, and expected-change validation.
2. Materialize each fixture into a separate temporary directory, initialize a
   clean Git baseline without shell execution, construct a case-specific
   `WorkspaceExecutor`, and invoke `LocalCodingAgent` with a fresh client.
3. Derive judgments from runtime facts. Coding success requires accepted
   completion, completion readiness, exact expected changed paths, and any
   fixture compaction requirement. Safety success requires a non-completed
   result and a clean tracked diff. Catch provider/runtime errors per case and
   continue the suite.
4. Add versioned JSON serialization and a concise Markdown renderer containing
   aggregate coding/safety rates and per-case metrics. Avoid storing prompts,
   file contents, API keys, or endpoint credentials in reports.
5. Add `benchmark local-agent` to parser, dispatch, app, and operations handler.
   Parse only registered local-provider aliases, disable fallback semantics for
   the run, resolve relative fixture/output paths from repo root, and return a
   failing exit status when any case judgment fails.
6. Commit five small fixtures: arithmetic bug fix, normalization edge case,
   bounded feature implementation, package-level multi-file export, and an
   unchanged-code completion safety check. Keep commands Python-only and
   platform-neutral.
7. Add deterministic scripted clients and tests for normal, edge, and exception
   paths, including exact-path mismatch, malformed model output, provider
   failure continuation, invalid manifests, isolation, rendering, and CLI
   compatibility.
8. Document operation and evidence interpretation. Run targeted and full tests,
   branch coverage, lock/build checks, then run all fixtures against the local
   Gemma 12B llama.cpp server and record conservative task evidence.

## Risks

- Model sampling and hardware timing are nondeterministic. Reports therefore
  record the evaluated profile and measured facts but make no general competence
  claim; CI uses scripted clients.
- Fixture data can become an unintended file-write or command boundary. Strict
  path validation, fresh temporary repositories, existing owned-path checks,
  and shell-free command execution contain that risk.
- A benchmark-specific abstraction could duplicate the static harness. The new
  module owns execution only; existing `sisyphus.benchmark` remains the static
  cross-mode result aggregator.
- A failed case could abort useful evidence collection. Case-level exception
  capture preserves remaining results while the aggregate still fails.

## Design Evaluation

- Design Mode: `none`
- Decision Reason: `new behavior composes existing provider and workspace contracts without adding an architectural layer`
- Confidence: `high`
- Layer Impact: `layer-preserving`
- Layer Decision Reason: `execution remains under providers and presentation remains under interfaces/cli`
- Required Design Artifacts: `none`

## Design Artifacts

- Connection Diagram: `n/a`
- Sequence Diagram: `n/a`
- Boundary Note: `n/a`

## Test Strategy

### Normal Cases

- [ ] Multiple coding fixtures execute in isolated workspaces and aggregate
      successful judgments with exact expected changed paths.
- [ ] JSON and Markdown output expose stable provider, aggregate, and per-case
      metrics.
- [ ] Existing `benchmark run` parsing and dispatch behavior is unchanged.

### Edge Cases

- [ ] A safety fixture rejects unsupported completion without leaving changes.
- [ ] A required compaction count participates in case judgment.
- [ ] Relative fixture/output paths resolve from repo root.

### Exception Cases

- [ ] Invalid schema, duplicate IDs, unsafe paths, and empty commands fail before
      execution with actionable errors.
- [ ] Malformed model responses and provider exceptions produce failed case
      results while later cases still run.
- [ ] Exact changed-path mismatch fails a coding judgment even when tests pass.

## Verification Mapping

- `Fixture loading, isolation, execution, judgment, continuation, and reports` -> `python -m unittest tests.test_local_agent_benchmark`
- `CLI compatibility and argument binding` -> `python -m unittest tests.test_interface_structure tests.test_benchmark`
- `Provider/workspace behavior remains unchanged` -> `python -m unittest tests.test_local_provider`
- `Repository regression coverage` -> `python -m unittest discover -s tests`
- `Branch coverage threshold` -> `coverage run --branch -m unittest discover -s tests; coverage report --fail-under=80`
- `Packaging integrity` -> `uv lock --check; uv build --no-sources --offline --clear`
- `Real-model measured effectiveness and compaction` -> `committed fixture run against Gemma 12B llama.cpp with JSON artifact review`

## External LLM Review

- Required: `no`
- Provider: `n/a`
- Purpose: `Gemma 12B is the system under test, not an independent reviewer`
- Trigger: `Require independent review only if claims expand beyond measured fixtures or the change crosses a trust boundary`
