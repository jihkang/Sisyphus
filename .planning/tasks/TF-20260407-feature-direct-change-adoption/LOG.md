# Log

## Timeline

- Created task.
- Implemented direct-change adoption through the request, API, daemon, and git helper paths.
- Added regression coverage for adoption provenance, parser flags, and request output.

## Notes

- The current implementation adopts modified, staged, and untracked files, plus tracked deletions.
- Internal `.planning` paths are excluded so taskflow does not adopt its own task metadata.

## Follow-ups

- Add base-branch selection so direct-change adoption and current-branch task creation can work together.
