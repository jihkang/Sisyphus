# Brief

## Task

- Task ID: `TF-20260517-feature-evidence-bound-evolution-loop`
- Type: `feature`
- Slug: `evidence-bound-evolution-loop`
- Branch: `feat/evidence-bound-evolution-loop`
- Backlog Order: `5/5`

## Problem

- Current evolution support is mostly read-only, planned, or manually driven.
- A stronger loop is desirable, but it is unsafe unless verify, MCP runtime, agent authority boundaries, and search authority ranking are already stable.
- Evolution must not let one broad-context model propose, review, accept, and promote its own changes.

## Desired Outcome

- Evolution runs are evidence-bound loops: dataset build, candidate proposal, isolated evaluation, evidence recording, review gate routing, and promotion through Sisyphus records.
- Candidates are constrained by owned paths, target contracts, verification obligations, and review gates.
- Promotion requires verified receipts and review decisions; no model self-approval.

## Acceptance Criteria

- [ ] Evolution loop stages have explicit input/output records and evidence refs.
- [ ] Candidate execution is isolated and does not mutate the live repo before promotion.
- [ ] Review gates are required before promotion eligibility.
- [ ] Promotion uses verified Sisyphus promotion records only.
- [ ] Failures record invalidation evidence rather than silently retrying or self-approving.

## Constraints

- Do this after backlog items 1-4.
- Do not weaken verify, review, or promotion authority for automation convenience.
- Keep every candidate bounded by target ids, owned paths, and explicit verification obligations.
