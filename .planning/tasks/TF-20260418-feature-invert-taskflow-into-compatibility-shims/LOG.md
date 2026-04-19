# Log

## Timeline

- 2026-04-18: Inspected the post-migration boundary and confirmed that CLI ownership still effectively sat under `taskflow`.
- 2026-04-18: Copied the CLI implementation into `src/sisyphus/cli.py`.
- 2026-04-18: Expanded the `taskflow` compatibility alias map so `taskflow.cli` resolves to `sisyphus.cli`.
- 2026-04-18: Extended compatibility regression coverage for legacy `taskflow` module identity and reran the focused runtime suite.

## Notes

- This slice defines completion in terms of runtime ownership and compatibility behavior, not deletion of every historical source file in `src/taskflow`.
- The authoritative implementation root is now `sisyphus` for CLI, MCP, evolution, and the previously moved core modules.
- Compatibility-sensitive behavior such as `.taskflow.toml` fallback remains intentionally supported.

## Follow-ups

- Optionally replace the remaining historical `src/taskflow/*.py` files with explicit tiny wrappers if we want the source tree itself to mirror the runtime alias boundary more literally.
- Once downstream users no longer depend on `taskflow`, we can consider a later removal task instead of keeping the compatibility package indefinitely.
