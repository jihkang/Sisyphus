# Repro

## Preconditions

- PR #64 is merged and `main` points to merge commit `6330966`.
- The canonical migration task is closed with verification passed and
  conformance green.

## Repro Steps

1. Open `docs/clean-architecture-implementation-debt.md` on merged `main`.
2. Observe that CA-11 is still listed as an open release gate.
3. Open the final review and observe that round 8, CI, merge, receipt, and
   merged-main revalidation are still described as pending.
4. Inspect the tracked review artifacts and observe that they end at round 7.

## Observed Result

- Repository documentation disagrees with the canonical closed task and merged
  GitHub state.

## Expected Result

- Round-8 evidence is tracked, CA-11 is completed, release gates are zero, and
  exactly two import-only compatibility shims remain as the complete debt list.

## Regression Test Target

- `tests.test_repository_hygiene` resolves the new local evidence links and
  `tests.test_architecture_dependencies` preserves the exact two-shim allowlist.
