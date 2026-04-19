# Brief

## Task

- Task ID: `TF-20260418-feature-define-evolution-to-sisyphus-handoff-payload`
- Type: `feature`
- Slug: `define-evolution-to-sisyphus-handoff-payload`
- Branch: `feat/define-evolution-to-sisyphus-handoff-payload`

## Problem

- The evolution slice needs a way to hand off promising candidates to Sisyphus without bypassing review gates or sneaking in implicit execution authority.
- Without a first-class handoff payload, the bridge layer will fall back to generic callbacks or ad hoc argument passing that operators cannot review clearly.
- This task must define the reviewable handoff contract before any bridge implementation begins.

## Desired Outcome

- The evolution layer has a typed, reviewable payload for follow-up task requests into Sisyphus.
- The payload carries enough context for operator review, later verification, and receipt linking.
- The payload makes the no-self-approval boundary explicit.

## Acceptance Criteria

- [ ] The handoff payload defines the fields needed for review and follow-up linkage: source run id, candidate id, target scope, instruction set, owned paths, expected verification obligations, evidence summary, and promotion intent.
- [ ] The contract makes clear that evolution may request follow-up work but may not approve the plan, freeze the spec, or trigger production execution on its own.
- [ ] The payload is documented as a reviewable request contract, not as an execution or receipt contract.

## Constraints

- Keep scope to the contract and integration-facing types only.
- Do not implement the actual bridge execution in this task.
- Re-read the task docs before verify and close.

## Spec Risks

- If the payload is too thin, operator review and later receipt linking will lack critical context.
- If the payload is too broad, it can accidentally encode execution authority rather than a request.
- If request and receipt semantics are mixed, later bridge code will conflate submission with completion.
