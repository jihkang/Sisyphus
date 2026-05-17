# Brief

## Task

- Task ID: `TF-20260517-issue-repair-search-context-mcp-runtime-surface`
- Type: `issue`
- Slug: `repair-search-context-mcp-runtime-surface`
- Branch: `fix/repair-search-context-mcp-runtime-surface`
- Backlog Order: `2/5`

## Symptom

- Source code and tests include search/context MCP tools and resources.
- A connected client can still fail on resources such as `repo://search/status` or `context://<pack-id>` with unsupported-resource behavior.
- The likely fault is runtime registration drift: launcher/bootstrap path, installed package, MCP adapter, or connected server instance may not expose the current core surface.

## Expected Behavior

- Connected MCP clients can discover and call search index rebuild, search, and context build tools.
- Connected MCP clients can read `repo://search/status` and persisted `context://<pack-id>` resources.
- Runtime bootstrap points at the repo-local current Sisyphus source or a clearly versioned installed package.
- Failure modes distinguish missing index, malformed index, missing pack, and stale server/runtime registration.

## Impact

- [ ] MCP search/context tools are discoverable through connected clients.
- [ ] MCP search/context resources are readable through connected clients.
- [ ] Bootstrap/runtime drift is detected or documented with actionable diagnostics.
- [ ] Existing MCP task, artifact, and evolution surfaces keep working.

## Notes

- Run after verify hardening.
- Do not redesign search ranking or ContextPack schema in this task.
