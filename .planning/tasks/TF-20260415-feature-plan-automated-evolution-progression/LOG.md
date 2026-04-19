# Log

## Timeline

- Created task
- Re-read the current evolution runner, self-evolution design doc, and current module boundaries before planning.
- Confirmed that `runner.py` still stops at run planning while dataset, harness execution, constraints, fitness, and report logic already exist separately.
- Narrowed the execution architecture: post-guard follow-up should create and run a dedicated Sisyphus task/worktree rather than calling an unrelated generic callback.

## Notes

- The next safe slice is orchestration plus guarded Sisyphus-managed follow-up execution, not direct mutation or MCP exposure.
- Self-hosted execution should reuse Sisyphus task creation, approval, freeze, provider launch, and isolated worktree management instead of introducing a parallel executor path.

## Follow-ups

- After the runner orchestration result model is stable, expose it over MCP and add approval-driven branch materialization as separate tasks.
