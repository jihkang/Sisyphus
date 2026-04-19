# Log

## Timeline

- Created replay follow-up task from the current root-adopted baseline.
- Linked the replay scope back to `TF-20260416-feature-implement-artifact-record-foundation`, which was already verified but blocked by a stale dirty worktree.

## Notes

- Adopted 2016 current changes from branch `feat/sisyphus-naming-unification` into the task worktree, including 49 deletions.
- This replay task preserves the original artifact-foundation boundary on top of the current `sisyphus` source-of-truth.
- Slot bindings, verification claims, runtime projection, promotion evaluation, invalidation routing, and MCP graph exposure remain later tasks.

## Follow-ups

- Layer slot-binding and verification-claim models on top of these record shapes instead of introducing parallel envelope formats.
- Use the typed lineage and invariant structures for runtime projection and promotion/invalidation tasks.
