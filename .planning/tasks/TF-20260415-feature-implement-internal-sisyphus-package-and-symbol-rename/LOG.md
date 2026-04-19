# Log

## Timeline

- Created task
- Inspected internal `taskflow` references, evolution package structure, and optional-dependency import behavior

## Notes

- A full physical move from `src/taskflow` to `src/sisyphus` is still higher risk than needed for this slice.
- Canonical `sisyphus.<submodule>` imports can be completed safely with package-level aliasing plus a small number of actual wrapper modules.
- Internal symbol names such as `TaskflowConfig` and `_is_internal_taskflow_path` are safe rename targets when compatibility aliases are preserved.

## Follow-ups

- Add canonical package aliases and internal symbol renames.
- Update tests and wrappers to prefer canonical imports.
- Keep persisted identifiers and legacy compatibility paths intact.
