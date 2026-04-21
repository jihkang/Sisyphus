# Plan

## Implementation Plan

1. Extend `promotion_state.py` so promotion requirement can be auto-classified and surfaced in the first-class promotion bundle.
2. Persist conversation path signals in task meta during daemon hydration so classification can distinguish promotable repo changes from test or planning-only work.
3. Cover default feature classification, non-feature fallback, test-only path exclusion, and explicit override precedence with regression tests.

## Risks

- The conversation request may omit edge conditions that still matter in the current codebase.
- The change may affect adjacent flows if the requested behavior touches shared state.

## Test Strategy

### Normal Cases

- [x] Conversation-created feature tasks default to `promotion.required=true`

### Edge Cases

- [x] Issue tasks and test-only feature paths stay `promotion.required=false`

### Exception Cases

- [x] Explicit `required_override` beats auto-classification without leaving stale promotion status behind

## Verification Mapping

- `Conversation-created feature tasks default to promotion.required=true` -> `python -m unittest tests.test_sisyphus`
- `Issue tasks and test-only feature paths stay promotion.required=false` -> `python -m unittest tests.test_sisyphus`
- `Explicit required_override beats auto-classification without leaving stale promotion status behind` -> `python -m unittest tests.test_sisyphus`

## External LLM Review

- Required: `no`
- Provider: `n/a`
- Purpose: `n/a`
- Trigger: `n/a`
