# Repro

## Preconditions

- Repository is checked out in the task worktree.
- The current branch reproduces the reported behavior.

## Repro Steps

1. Follow the workflow described by the request: Measure MCP and promotion value.
2. Observe the current incorrect behavior in the relevant code path.
3. Compare the observed result against the expected result below.

## Observed Result

- Follow up from umbrella issue TF-20260420-issue-assess-third-party-critique-of-sisyphus-codebase. Define and instrument the minimum metrics needed to judge whether MCP stabilization and promotion workflow are worth the added ceremony. At minimum capture session resume time, reopen rate after verify, promotion lead time, and manual intervention count.

## Expected Result

- The reported issue no longer occurs once the fix is applied.

## Regression Test Target

- Add or update a regression-oriented test that fails before the fix and passes after it.
