# Log

## Timeline

- Created task
- Inspected current entrypoint, config, discovery, MCP launcher, and doc surfaces for the next migration slice

## Notes

- Canonical product naming is already visible to users, but direct module entrypoints still resolve through `taskflow.*`.
- `.sisyphus.toml` support does not exist yet, so both config loading and repo discovery still anchor on `.taskflow.toml`.
- This slice is safe as long as `taskflow` compatibility remains intact and protocol/persisted identifiers remain unchanged.

## Follow-ups

- Add canonical module wrappers and move console entrypoints to them.
- Add dual-read config/discovery support.
- Update launcher docs and examples to the canonical module path.
