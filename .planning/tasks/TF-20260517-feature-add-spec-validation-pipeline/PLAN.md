# Plan

## Implementation Plan

1. Add a deterministic spec validation layer.
   - Introduce a reusable validator, preferably `src/sisyphus/spec_validation.py`, that can load a task record plus task docs and return a structured report.
   - Report shape: `task_id`, `status`, `checked_at`, `source_fingerprint`, `findings`, `summary`, and `gate_codes`.
   - Finding shape: `code`, `severity`, `source`, `message`, `doc`, optional `section`, optional `remediation`.

2. Define the MVP rule set.
   - Required docs: feature tasks require BRIEF and PLAN; issue tasks require BRIEF, REPRO, and FIX_PLAN when present in metadata.
   - Required sections: BRIEF must define problem, outcome, acceptance criteria, and constraints; PLAN/FIX_PLAN must define implementation plan, risks, design evaluation, test strategy, verification mapping, and external review policy.
   - Placeholder detection: reject default/generated placeholders such as generic requested workflow text, `Criterion 1`, `Note 1`, `Follow-up 1`, `n/a` where a concrete answer is required, and empty checkbox-only strategy items.
   - Scope clarity: require owned paths or explicit scope notes, plus out-of-scope notes when the request touches shared lifecycle behavior.
   - Coverage: require at least one normal, edge, and exception case unless an explicit waiver is present with a reason.
   - Verification mapping: each coverage case must map to at least one concrete verification method, and each method must name a command, test, manual review artifact, or external review trigger.
   - Design consistency: layer-adding or layer-reshaping work cannot use `design_mode=none`; required artifacts must be referenced when design mode requires them.
   - External LLM policy: if required, provider, purpose, trigger, and expected artifact must be present; if not required, the reason must be explicit for agent/review/evolution-sensitive work.
   - Dependency ordering: backlog tasks can declare prerequisite task IDs and should warn when a declared prerequisite is not approved/frozen or merged.
   - Waivers: docs-only/design-only waivers must be explicit, reasoned, and scoped to a specific rule.

3. Persist validation reports.
   - Store the latest report at `artifacts/spec-validation/latest.json` under the task directory.
   - Include doc fingerprints so stale reports can be detected after BRIEF/PLAN/REPRO/FIX_PLAN changes.
   - Keep human output generated from the report instead of writing a second authoritative markdown spec.

4. Integrate lifecycle gates.
   - `approve_task_plan` should run validation and block with `SPEC_VALIDATION_FAILED` when severity `error` findings exist.
   - `freeze_task_spec` should run validation again, refresh task strategy/design metadata from docs where appropriate, and block stale or failing reports before freezing the anchor.
   - `enforce_spec_frozen` and `run_verify` should treat a missing/stale/failing validation report as a spec gate for non-legacy draft tasks.
   - Existing doc/spec gates in `audit.py` should either delegate to the validator or be reduced to compatibility wrappers to avoid divergent rule definitions.

5. Add operator surfaces.
   - CLI: add `sisyphus spec validate <task-id>` with normal text output and `--json` output.
   - MCP tool: add `sisyphus.spec_validate` with the same report payload.
   - MCP resource: add `task://{task_id}/spec-validation` for the latest persisted report.
   - Status output should show whether the latest validation is missing, passed, failed, or stale when available.

6. Add focused tests before broad rollout.
   - Passing concrete feature spec produces a passed report.
   - Generated placeholder feature spec fails before plan approval.
   - Missing normal/edge/exception coverage fails or requires a waiver.
   - Unmapped verification case fails.
   - Layer-adding work with `design_mode=none` fails.
   - Required external review policy fields fail when omitted.
   - Explicit waiver passes only when it includes rule, reason, and scope.
   - `plan approve`, `spec freeze`, and `verify` block on failing or stale validation.

7. Preserve compatibility.
   - Do not retroactively block already frozen legacy tasks unless the operator explicitly validates, re-approves, re-freezes, or executes a path that requires refreshed validation.
   - Keep report writes task-local and deterministic.
   - Avoid network, provider calls, or semantic LLM scoring in this first slice.

## Risks

- Overly broad rules could block legitimate small tasks. Mitigation: start with deterministic structural checks, warnings for ambiguous quality issues, and explicit scoped waivers.
- Lifecycle integration touches shared planning and audit paths. Mitigation: keep validator pure, centralize gate conversion, and cover plan approve/freeze/verify with regression tests.
- Existing generated tasks may fail validation. Mitigation: only enforce strictly on draft or newly validated lifecycle transitions, not on already frozen legacy tasks by default.
- Design metadata currently lives both in docs and task records. Mitigation: make freeze-time sync explicit and add tests for doc-to-record alignment where validation depends on design fields.

## Design Evaluation

- Design Mode: `light`
- Decision Reason: `adds a lifecycle validation layer and shared gate/report contract`
- Confidence: `medium`
- Layer Impact: `layer-adding`
- Layer Decision Reason: `introduces a spec-validation layer used by planning, freeze, verify, CLI, and MCP`
- Required Design Artifacts: `none`

## Design Artifacts

- Connection Diagram: `n/a`
- Sequence Diagram: `n/a`
- Boundary Note: `Validator is the only owner of spec-validation rules. Planning, audit, CLI, and MCP call the validator and render its report; they should not define competing rule logic.`

## Test Strategy

### Normal Cases

- [ ] Concrete feature spec validates successfully and persists a fresh report
- [ ] `plan approve` and `spec freeze` proceed when the validation report has no error findings

### Edge Cases

- [ ] Minimal valid task passes only when every required section, coverage class, and verification mapping is present
- [ ] Docs-only or design-only task passes only with an explicit scoped waiver
- [ ] Already frozen legacy task is not retroactively blocked until a validating lifecycle action is invoked

### Exception Cases

- [ ] Generated placeholder spec fails with actionable finding codes
- [ ] Missing verification mapping fails before plan approval and before spec freeze
- [ ] Stale validation report blocks freeze or verify until refreshed
- [ ] Layer-adding work with `design_mode=none` fails validation

## Verification Mapping

- `Concrete feature spec validates successfully and persists a fresh report` -> `targeted unit test`
- `plan approve and spec freeze proceed when the validation report has no error findings` -> `targeted lifecycle regression test`
- `Minimal valid task passes only when every required section, coverage class, and verification mapping is present` -> `targeted unit test`
- `Docs-only or design-only task passes only with an explicit scoped waiver` -> `targeted unit test`
- `Already frozen legacy task is not retroactively blocked until a validating lifecycle action is invoked` -> `targeted lifecycle regression test`
- `Generated placeholder spec fails with actionable finding codes` -> `targeted unit test`
- `Missing verification mapping fails before plan approval and before spec freeze` -> `targeted lifecycle regression test`
- `Stale validation report blocks freeze or verify until refreshed` -> `targeted lifecycle regression test`
- `Layer-adding work with design_mode=none fails validation` -> `targeted unit test`

## External LLM Review

- Required: `no`
- Provider: `n/a`
- Purpose: `not needed for this deterministic first slice`
- Trigger: `future semantic/spec-quality review can be added after deterministic validation exists`

## Ordering

- This task must be completed before `TF-20260517-feature-harden-verify-defaults-and-strategy-gates`.
- Search, evolution, and agent-review authority work remain downstream because they depend on trusted task specs and validation diagnostics.
