# Log

## Timeline

- Created task
- Inspected naming references across packaging, CLI, docs, MCP setup, config loading, event schema, and tests
- Reframed the task as a planning-only migration design rather than an implementation slice
- Recorded a phased naming-unification plan with compatibility boundaries
- Narrowed execution to the first safe rename slice: CLI/help, generated wording, and compatibility-path documentation

## Notes

- `Sisyphus` is already the public-facing product name in many docs, but the CLI parser and generated task docs still expose `taskflow`.
- `taskflow.mcp_server` is a real current launcher path, so docs must describe it accurately until a new module path exists.
- The highest-risk rename targets remain `src/taskflow/`, `.taskflow.toml`, `taskflow.event.v1`, and persisted task identifiers such as `TF-...`.

## Follow-ups

- Implement the safe user-facing surface cleanup.
- Keep compatibility-only surfaces for later slices.
- Revisit package/config/protocol renames only after shim infrastructure exists.
