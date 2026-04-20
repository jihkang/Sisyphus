# Log

## Timeline

- Created task
- Confirmed that only the follow-up request contract exists today; no bridge implementation currently converts evolution results into reviewable Sisyphus tasks.
- Replaced the generic plan with a concrete bridge scope centered on request-only handoff and authority-boundary enforcement.
- Implemented the request-only bridge helper and added regression coverage for lineage attachment, review-gate preservation, and privileged-flag rejection.

## Notes

- `src/sisyphus/evolution/handoff.py` already defines `EvolutionFollowupRequest`, review gates, and the disallowed permission flags the bridge must enforce.
- `src/sisyphus/api.py`, `src/sisyphus/daemon.py`, and task metadata already support `source_context`, requested slug tracking, and follow-up linkage hooks that the bridge can reuse.
- `src/sisyphus/evolution/bridge.py` now converts `EvolutionFollowupRequest` into a reviewable Sisyphus task request with evolution lineage, evidence summaries, and verification obligations attached in source context.
- `tests.test_evolution` now covers successful request bridging, review-gate order preservation, privileged-flag rejection, and missing-evidence rejection.

## Follow-ups

- After this bridge lands, the next slices are execution receipt linkage and verification-artifact attachment.
