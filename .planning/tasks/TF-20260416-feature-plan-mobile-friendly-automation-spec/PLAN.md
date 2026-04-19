# Plan

## Implementation Plan

1. Inspect the existing mobile-friendly seams in the repository.
   - Review `discord_bot`, `service`, `workflow`, and `api` in the Sisyphus runtime.
   - Review the bundled `cc` remote/mobile session commands to understand what already exists for phone/browser drill-down.

2. Draft a concrete automation spec.
   - Define the product goal, operator flows, trigger model, action model, notification contract, and safety policy.
   - Anchor the spec to current implementation seams so the document can drive real follow-up work.

3. Turn the spec into an implementation roadmap.
   - Break the work into MVP slices.
   - Make the first slice explicitly phone-first and low-risk.

4. Update repository discoverability and task docs.
   - Add the spec to `docs/`.
   - Add a README pointer.
   - Rewrite the task docs so verify/close reflect the actual planning deliverable.

## Risks

- The repository already contains two different mobile-adjacent surfaces, so the spec could accidentally duplicate instead of unify them.
- A vague "automation" spec could overreach into autonomous git/release behavior and become unsafe.
- If the primary phone surface is chosen incorrectly, the first implementation slice will stall on infrastructure rather than operator value.

## Test Strategy

### Normal Cases

- [ ] The spec clearly describes the phone-first operator loop and names the primary mobile surface.
- [ ] The spec defines a practical MVP that can be built on the current codebase.

### Edge Cases

- [ ] The spec explains how deep drill-down works without making it mandatory for routine monitoring.
- [ ] The spec distinguishes read-only notifications from write-capable automation actions.

### Exception Cases

- [ ] The spec explicitly excludes unsafe or out-of-scope automation behavior.
- [ ] The spec does not assume a hosted database or brand-new native app for MVP.

## Verification Mapping

- `The spec clearly describes the phone-first operator loop and names the primary mobile surface.` -> `manual review of docs/mobile-automation-spec.md`
- `The spec defines a practical MVP that can be built on the current codebase.` -> `manual review against src/taskflow/discord_bot.py, src/taskflow/service.py, src/taskflow/workflow.py, src/taskflow/api.py`
- `The spec explains drill-down, safety scope, and out-of-scope behavior correctly.` -> `manual review against cc/commands/session/session.tsx and cc/hooks/useRemoteSession.ts`
- `The repository points readers to the new spec.` -> `rg -n "mobile-automation-spec" README.md docs`

## External LLM Review

- Required: `no`
- Provider: `n/a`
- Purpose: `n/a`
- Trigger: `n/a`
