# RL Action Space

Sisyphus exposes an explicit action registry in `src/sisyphus/action_space.py`.

The registry defines:

- action name
- risk level
- whether a policy may choose it
- whether human judgment is required
- whether the action mutates state
- optional lifecycle action mapping

## Risk Levels

`ActionRiskLevel`:

- `read_only`: reads state or context
- `low_risk_write`: writes bounded workflow state after validation
- `review_gated`: requires operator or reviewer judgment
- `human_only`: should not be selected by an autonomous policy

## Policy-Allowed Actions

Examples:

- `sisyphus.get_task`
- `sisyphus.read_resource`
- `sisyphus.search`
- `sisyphus.context_build`
- `sisyphus.list_agents`
- `sisyphus.plan_revise`
- `sisyphus.subtasks_generate`
- `sisyphus.verify_task`

These are still gated by lifecycle rules when they map to a lifecycle transition.

## Review-Gated Actions

Examples:

- `sisyphus.plan_request_changes`
- `sisyphus.plan_approve`
- `sisyphus.spec_freeze`
- `sisyphus.close_task`

These require review or operator judgment. They may appear in observations as forbidden actions with gates and reasons.

## Human-Only Actions

Examples:

- `sisyphus.execute_promotion`
- `sisyphus.record_merged_pr`

These interact with promotion or external repository state and remain outside policy automation.

## Observation Integration

The observation renderer exposes:

- `allowed_next_actions`
- `forbidden_next_actions`

That lets a worker choose from the environment-provided action set rather than inventing workflow transitions.
