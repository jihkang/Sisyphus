# Brief

## Task

- Task ID: `TF-20260420-feature-connect-verification-artifact-to-evolution-claims`
- Type: `feature`
- Slug: `connect-verification-artifact-to-evolution-claims`
- Branch: `feat/connect-verification-artifact-to-evolution-claims`

## Problem

- The follow-up bridge and receipt-linkage slices are now in place, but the system still does not turn declared follow-up verification obligations into actual evolution `VerificationArtifact` records.
- `EvolutionFollowupRequest` already carries `expected_verification_obligations`, and `receipts.py` can now project executed follow-up receipts and task runs. This task must connect those two layers.
- The mapper must fail clearly when obligations are missing or when receipt linkage is absent, instead of inventing verification success.

## Desired Outcome

- An executed evolution follow-up task can be projected into stable `VerificationArtifact` records derived from the declared verification obligations and linked receipt evidence.
- Verification artifacts preserve both the obligation claim and the verification method, and they reflect pass/fail based on the actual follow-up task execution state.
- The mapping remains receipt-and-claim only; it does not add promotion or invalidation decisions.

## Acceptance Criteria

- [ ] A verification-linkage helper maps follow-up obligations plus linked receipt evidence into `VerificationArtifact` records.
- [ ] Verification artifact results are derived from real follow-up execution state rather than assumed success.
- [ ] Missing obligations or missing linked receipt evidence fail with actionable errors.

## Constraints

- Preserve existing repository conventions unless the task requires a deliberate change.
- Re-read the task docs before verify and close.
- Do not add promotion/invalidation decisions in this slice.
