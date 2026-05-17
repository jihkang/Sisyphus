# Brief

## Task

- Task ID: `TF-20260517-feature-harden-verify-defaults-and-strategy-gates`
- Type: `feature`
- Slug: `harden-verify-defaults-and-strategy-gates`
- Branch: `feat/harden-verify-defaults-and-strategy-gates`
- Backlog Order: `1/5`

## Problem

- Sisyphus can currently mark some work verified even when `verify_commands` is empty.
- Test strategy checkboxes can become true without durable command/evidence linkage strong enough to justify verification.
- This weakens every later workflow, including MCP repair, search ranking, agent authority boundaries, and evolution, because they depend on Sisyphus verification as an authority signal.

## Desired Outcome

- Feature and implementation tasks fail closed when no effective verification commands or explicit evidence-backed verification methods exist.
- Design-only or documentation-only tasks can still verify without commands only when explicitly classified and justified.
- Verification updates normal, edge, and exception test strategy items only from concrete command/evidence outcomes or explicit waivers.
- Failed verification surfaces actionable gate codes instead of silently passing.

## Acceptance Criteria

- [ ] Feature tasks with empty `verify_commands` fail verification unless explicitly marked design/docs-only with a waiver reason.
- [ ] Verification requires at least one concrete command result or explicit evidence-backed method for implementation tasks.
- [ ] Test strategy items are checked only when corresponding verification evidence exists or an explicit waiver is recorded.
- [ ] `sisyphus verify` emits clear gates for empty command config, unchecked strategy items, and missing evidence.
- [ ] Existing valid tasks with configured verify commands continue to pass.
- [ ] Unit and integration tests cover normal, edge, and exception behavior.

## Constraints

- Do not break intentionally design-only issue/spec tasks.
- Keep the policy repo-local and deterministic; do not require external services.
- Preserve current task lifecycle transitions except where verification previously passed without evidence.
