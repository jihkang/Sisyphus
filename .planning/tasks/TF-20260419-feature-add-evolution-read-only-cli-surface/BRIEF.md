# Brief

## Task

- Task ID: `TF-20260419-feature-add-evolution-read-only-cli-surface`
- Type: `feature`
- Slug: `add-evolution-read-only-cli-surface`
- Branch: `feat/add-evolution-read-only-cli-surface`

## Problem

- Evolution contracts, run artifacts, and reports now exist, but there is still no operator-facing CLI for `run`, `status`, `report`, and `compare`.
- The current system requires direct code or file inspection to see evolution outputs, which prevents a usable read-only surface over the existing artifact cycle.
- This slice must stay read-only: no follow-up execution, no promotion, and no self-approval commands.

## Desired Outcome

- Operators can run evolution planning/evaluation through CLI entrypoints and inspect stored runs through `status`, `report`, and `compare`.
- The CLI surface reads existing evolution artifacts and renders them consistently without mutating live repo state beyond the bounded run artifacts that the orchestrator already owns.
- The command surface is explicitly limited to read-only/operator inspection behavior.

## Acceptance Criteria

- [x] `sisyphus evolution run`, `status`, `report`, and `compare` exist and map onto current evolution contracts/artifacts.
- [x] The new commands stay read-only and do not expose promotion or follow-up execution actions.
- [x] Regression tests cover command parsing and representative output loading/rendering paths.

## Constraints

- Preserve existing repository conventions unless the task requires a deliberate change.
- Re-read the task docs before verify and close.
- Do not couple this slice to MCP surface or event-bus changes; keep it as CLI-only read-side work.
