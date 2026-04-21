# Brief

## Task

- Task ID: `TF-20260421-feature-promotion-state-machine-and-task-schema`
- Type: `feature`
- Slug: `promotion-state-machine-and-task-schema`
- Branch: `feat/promotion-state-machine-and-task-schema`

## Problem

- Add promotion state machine and task schema
- Original request: Follow up from umbrella issue TF-20260420-issue-assess-third-party-critique-of-sisyphus-codebase. Extend task state with a first-class promotion block and status machine. Minimum schema should cover required, status, strategy, parent_artifact_id, parent_task_id, base_branch, head_branch, pr_number, pr_url, and receipt_path so verify/close/promotion can coordinate on one contract.

## Desired Outcome

- Every task has a first-class `promotion` bundle in task state instead of relying on ad hoc `meta["promotion"]` fields.
- Merge-receipt recording, MCP projections, service summaries, and evolution receipt readers all read the same promotion contract.
- Legacy `meta["promotion"]` data continues to load, but it is normalized into the first-class promotion bundle.

## Acceptance Criteria

- [x] Task records default and normalize a first-class promotion block with required/status/strategy/lineage/branch/PR/receipt fields.
- [x] Existing merge-receipt recording updates the first-class promotion bundle and keeps legacy meta compatibility.
- [x] MCP task/status projections, service summaries, and evolution follow-up receipt readers use the normalized promotion state.
- [x] Focused and broader regression suites pass after the schema/state-machine change.

## Constraints

- Preserve existing repository conventions unless the task requires a deliberate change.
- Re-read the task docs before verify and close.
