# Log

## Timeline

- Created task
- Replaced the generic receipt-linkage scaffold with a concrete scope centered on executed evolution follow-up tasks and hard-state receipt projection.
- Implemented evolution follow-up execution projection and added regression coverage for verify-receipt linkage, optional promotion receipt inclusion, and missing-receipt failures.

## Notes

- The bridge slice now creates evolution follow-up tasks with source-context lineage, but it does not yet map later task execution back into evolution receipt artifacts.
- Core artifact projection already defines `TaskRunRef` from verify results, so this slice should reuse that run-id convention instead of inventing a second one.
- Promotion receipt linkage is allowed only as optional receipt evidence; promotion decisions remain out of scope.
- `src/sisyphus/evolution/receipts.py` now projects a bridged follow-up task into `ExecutionReceiptArtifact` and `TaskRunRef` data anchored to the source evolution run.
- `tests.test_evolution` now covers successful verify receipt projection, optional promotion receipt projection, missing verify results, and missing promotion receipt failure.

## Follow-ups

- After this slice, the next evolution step is verification-artifact linkage from follow-up execution back to evolution claims.
