# Reproduction

## Scenario

1. Start or connect to the Sisyphus MCP server through the user-facing bootstrap.
2. List tools/resources from the connected client.
3. Try reading `repo://search/status`.
4. Build a ContextPack and try reading `context://<context-pack-id>`.

## Observed Risk

- Source tests can pass while the connected runtime still reports search/context resources as unsupported.

## Expected Guard

- Runtime discovery and resource reads match source-level MCP core behavior, or diagnostics explicitly identify a stale server/bootstrap path.
