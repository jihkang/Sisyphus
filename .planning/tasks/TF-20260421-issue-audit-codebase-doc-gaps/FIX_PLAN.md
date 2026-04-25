# Fix Plan

## Root Cause Hypothesis

- Documentation and implementation had drifted in a few areas, and the repository did not yet have a compact audit record of which gaps were still real versus already shipped.

## Fix Strategy

1. Read the relevant architecture, evolution, artifact, and mobile automation docs against the current repository code.
2. Separate already-implemented surfaces from still-missing surfaces so the audit does not overstate drift.
3. Group the remaining work into concrete follow-up themes that can become feature tasks later.
4. Capture the verified audit summary in the task docs.

## Audit Summary

- `Adaptive planning / design-layer evaluation`
  - Status: `implemented during follow-up work`
  - Notes: planning, state projection, conformance, and verify-time replan logic were added after the original audit pass.
- `Promotion lifecycle`
  - Status: `implemented during follow-up work`
  - Notes: promotion state, promotable classification, close gating, executor wiring, receipt handoff, stacked base resolution, and measurement hooks landed during follow-up work.
- `Adaptive multi-provider agent layer`
  - Status: `still missing`
  - Notes: the repository still behaves like a tracked subprocess wrapper with a Codex-first launch path rather than a full adaptive provider layer across Codex, Claude, Hermes, or OpenClaw-style runtimes.
- `Mobile automation MVP`
  - Status: `still missing`
  - Notes: the docs describe a larger automation surface than the current repository implements.
- `Durable artifact layer`
  - Status: `still missing`
  - Notes: feature/artifact projection exists, but a durable typed artifact layer with broader lifecycle handling remains future work.

## Remaining Follow-up Themes

- Build the adaptive agent/provider layer as a first-class execution abstraction instead of relying on a Codex-centric wrapper.
- Implement the mobile automation MVP that the existing docs describe.
- Finish the durable artifact layer beyond read-only projection/evaluation.
- Sync shared architecture docs only after those implementations land.

## Test Strategy

### Normal Cases

- [x] The audit identifies concrete remaining work instead of mixing shipped and unshipped surfaces

### Edge Cases

- [x] Follow-up work already landed after the first audit pass is not misreported as still missing

### Exception Cases

- [x] The summary explicitly calls out uncertainty boundaries instead of inventing implementation status

## Verification Mapping

- `The audit identifies concrete remaining work instead of mixing shipped and unshipped surfaces` -> `manual review`
- `Follow-up work already landed after the first audit pass is not misreported as still missing` -> `manual review`
- `The summary explicitly calls out uncertainty boundaries instead of inventing implementation status` -> `manual review`

## External LLM Review

- Required: `no`
- Provider: `n/a`
- Purpose: `n/a`
- Trigger: `n/a`
