# Verify

## Audit Summary

- Attempt: `0/10`
- Status: `not_run`
- Result: `implementation has not started; commands below are the frozen verification contract`

## Commands

- [ ] `uv lock --check`
- [ ] `uv run --frozen python -m unittest tests.test_architecture_dependencies tests.test_interface_structure tests.test_repository_hygiene -v`
- [ ] `uv run --frozen python -m unittest tests.test_persistence tests.test_path_security tests.test_inbox_events tests.test_lifecycle_rules tests.test_spec_validation tests.test_workflow_candidates -v`
- [ ] `uv run --frozen python -m unittest tests.test_sisyphus tests.test_mcp_core tests.test_mcp_server tests.test_evolution -v`
- [ ] `uv run --frozen python -m unittest discover -s tests -v`
- [ ] `uv run --frozen --all-extras --group dev coverage run -m unittest discover -s tests`
- [ ] `uv run --frozen --all-extras --group dev coverage report --fail-under=80`
- [ ] `uv build --no-sources`
- [ ] `uv build --no-sources --offline` when the locked build requirements are cached
- [ ] Install the built wheel into an isolated environment outside the source tree and smoke-test Python, CLI, and MCP imports.
- [ ] `git diff --check`
- [ ] Run Sisyphus spec validation, conformance review, task verify, GitHub CI, merged-main revalidation, and merge-receipt recording.

## Results

### Command Results

- All commands are pending implementation.

### Test Coverage Check

- [ ] Normal cases covered
- [ ] Edge cases covered
- [ ] Exception cases covered
- [ ] Port fakes and concrete adapters pass the same contract suite
- [ ] Baseline and migrated observable outputs are equivalent
- [ ] Architecture allowlist is empty at final verification

### Design Assessment

- Mode: `full`
- Layer impact: `layer-adding`
- Status: `not_assessed`
- Replan required: `no`
- Missing artifacts: `none`
- Summary: `Assessment occurs after implementation against the frozen dependency, sequence, and authority artifacts.`

### External LLM Review

- Required: `yes`
- Status: `pending`
- Notes: `Independent review is required after tests pass and before final promotion.`

## Gates

- Plan approval and spec freeze remain operator decisions.
- No implementation phase starts while conformance is yellow/red or spec validation has blocking findings.
- No child slice merges with new architecture violations or observable compatibility drift.
