# Changeset

## Summary

- Added execution-purpose ContextPack construction with current-task exclusion and source/purpose metadata.
- Loaded the persisted ContextPack into Codex worker prompts before task docs as supporting evidence.
- Added regression coverage for prompt loading, current-task exclusion, missing/malformed index behavior, empty packs, CLI compatibility, and invalid persisted ContextPack schemas.

## Verification

- `python -m unittest tests.test_search_context -v` -> passed, 13 tests
- `python -m unittest discover -s tests -p 'test_*.py' -v` -> passed, 304 tests
