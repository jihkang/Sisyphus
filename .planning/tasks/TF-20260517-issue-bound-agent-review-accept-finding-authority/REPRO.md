# Reproduction

## Scenario

1. A worker receives a broad prompt containing task docs, prior evidence, and retrieved context.
2. The same model proposes review findings, decides whether those findings are satisfied, and implies promotion readiness.
3. A finding or acceptance claim is made without an explicit source ref, artifact id, verification claim, or command receipt.

## Observed Risk

- The system can treat a broad-context model statement as if it were verified task memory.
- Acceptance and promotion can inherit hallucinated findings or stale evidence.

## Expected Guard

- Findings without evidence refs are non-authoritative.
- Acceptance requires mapped obligations and verified evidence.
- Promotion uses verification/promotion records and review gates, not raw agent judgment.
