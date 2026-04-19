# Log

## Timeline

- Created task
- Fast-forwarded the task worktree onto the current local baseline so the handoff contract work would target the current naming surface.
- Added `src/taskflow/evolution/handoff.py` to define the reviewable follow-up request, evidence summary, and verification obligation types.
- Exported the new handoff contract through `taskflow.evolution` and `sisyphus.evolution`, and documented the no-self-approval boundary in the architecture docs.

## Notes

- The handoff payload now carries source run id, candidate id, target scope, instruction set, owned paths, verification obligations, evidence summary, and promotion intent.
- The payload is explicitly request-only and keeps plan approval, spec freeze, provider execution, and promotion authority disabled.
- Receipt and verification artifacts remain downstream Sisyphus responsibilities rather than fields that complete the request.

## Follow-ups

- Connect this request contract to the later bridge task without adding implicit execution authority.
- Use the same payload shape when the read-only orchestrator begins emitting follow-up candidates.
