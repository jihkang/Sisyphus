# Brief

## Task

- Task ID: `TF-20260517-issue-bound-agent-review-accept-finding-authority`
- Type: `issue`
- Slug: `bound-agent-review-accept-finding-authority`
- Branch: `fix/bound-agent-review-accept-finding-authority`
- Backlog Order: `3/5`

## Symptom

- Sisyphus agent workflows can drift toward one large model performing review finding generation, acceptance decisions, and promotion judgment over broad task context.
- That creates the same memory-overreach risk as raw multi-turn memory: findings can be invented from implicit context, acceptance can treat retrieved evidence as authority, and promotion can conflate planner/executor claims with verified artifacts.
- This issue tracks a bounded authority design so agent review/accept/finding stages are evidence-bound and role-separated.

## Expected Behavior

- Review findings reference explicit source refs, ContextPack items, task docs, artifact records, verification claims, or command receipts.
- Acceptance decisions evaluate mapped obligations and evidence, not raw model recollection.
- Promotion decisions depend on verified task/artifact state and review gates, not on a single model's broad-context judgment.
- The design defines which role can propose, review, accept, invalidate, or promote, and what evidence each action must cite.

## Impact

- [ ] Agent review/finding/acceptance responsibilities are separated by stage and authority.
- [ ] Findings and acceptance decisions require evidence refs instead of raw memory.
- [ ] Promotion judgment remains bound to verification/promotion records.
- [ ] Existing agent execution flows keep working while the authority model is tightened.

## Notes

- This is a follow-up design/implementation task, not part of the ContextPack prompt-loading slice.
- Run after verify hardening and MCP runtime surface repair.
- Prefer ContextPack and source refs as inputs, but keep frozen task docs and verification records as authority.
