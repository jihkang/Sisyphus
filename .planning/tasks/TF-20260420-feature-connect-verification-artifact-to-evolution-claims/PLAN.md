# Plan

## Implementation Plan

1. Inspect the new follow-up receipt projection layer, the follow-up source-context obligation shape, and the current `VerificationArtifact` contract to determine the smallest stable linkage layer.
2. Implement an evolution verification projection helper that validates follow-up lineage, loads linked receipts/task runs, reads declared verification obligations, and emits `VerificationArtifact` records.
3. Extend the verification artifact shape only as much as needed to preserve the obligation method in hard state.
4. Add focused tests for passed obligation mapping, failed obligation mapping when follow-up verification fails, and failure cases for missing obligations or missing linked receipts.
5. Update task docs and verification notes to match the implemented verification-linkage behavior.

## Risks

- The current `VerificationArtifact` contract stores claim/scope/result but not the obligation method, so this slice may need a narrow schema extension.
- If verification linkage treats any follow-up task as evolution-managed without checking follow-up lineage, it will over-project normal Sisyphus tasks.
- If failed verify results are collapsed into a passing verification artifact, the evolution graph will drift away from actual execution evidence.

## Test Strategy

### Normal Cases

- [ ] A follow-up task with declared obligations and passing verify results projects into `VerificationArtifact` records that preserve the obligation claim, method, and linked receipt evidence.
- [ ] A follow-up task with failing verify results still produces verification artifacts, but they are marked as failed instead of passed.

### Edge Cases

- [ ] Verification linkage uses only the evolution follow-up source-context obligation list and ignores unrelated source-context keys.
- [ ] Multiple obligations map to stable artifact ids and share linked receipt evidence without duplicating or dropping records unpredictably.

### Exception Cases

- [ ] A bridged follow-up task with no declared verification obligations fails clearly instead of fabricating verification artifacts.
- [ ] A follow-up task whose linked receipts cannot be projected fails with an actionable missing-receipt error.

## Verification Mapping

- `A follow-up task with declared obligations and passing verify results projects into VerificationArtifact records that preserve the obligation claim, method, and linked receipt evidence.` -> `env PYTHONDONTWRITEBYTECODE=1 /tmp/sisyphus-venv-fresh/bin/python -m unittest -q tests.test_evolution`
- `A follow-up task with failing verify results still produces verification artifacts, but they are marked as failed instead of passed.` -> `env PYTHONDONTWRITEBYTECODE=1 /tmp/sisyphus-venv-fresh/bin/python -m unittest -q tests.test_evolution`
- `Verification linkage uses only the evolution follow-up source-context obligation list and ignores unrelated source-context keys.` -> `env PYTHONDONTWRITEBYTECODE=1 /tmp/sisyphus-venv-fresh/bin/python -m unittest -q tests.test_evolution`
- `Multiple obligations map to stable artifact ids and share linked receipt evidence without duplicating or dropping records unpredictably.` -> `env PYTHONDONTWRITEBYTECODE=1 /tmp/sisyphus-venv-fresh/bin/python -m unittest -q tests.test_evolution`
- `A bridged follow-up task with no declared verification obligations fails clearly instead of fabricating verification artifacts.` -> `env PYTHONDONTWRITEBYTECODE=1 /tmp/sisyphus-venv-fresh/bin/python -m unittest -q tests.test_evolution`
- `A follow-up task whose linked receipts cannot be projected fails with an actionable missing-receipt error.` -> `env PYTHONDONTWRITEBYTECODE=1 /tmp/sisyphus-venv-fresh/bin/python -m unittest -q tests.test_evolution`

## External LLM Review

- Required: `no`
- Provider: `n/a`
- Purpose: `n/a`
- Trigger: `n/a`
