# Plan

## Implementation Plan

1. Update the canonical user-facing command surface.
   - Change `build_parser()` to present `sisyphus` as the CLI program name.
   - Preserve runtime behavior for the existing `taskflow` console alias.

2. Update generated task-doc guidance.
   - Replace `taskflow verify` with `sisyphus verify` in the feature and issue verification mapping renderers.
   - Keep all functional workflow semantics unchanged.

3. Clarify compatibility-only MCP launcher wording in docs.
   - Update MCP setup docs and wrapper READMEs to explain that `python -m taskflow.mcp_server` remains the current compatibility launcher path.
   - Avoid changing code examples to a nonexistent `sisyphus.mcp_server` module in this slice.

4. Add regression coverage and verify the slice.
   - Add tests for the parser program name and generated-plan wording.
   - Run the targeted unittest file covering the affected rendering and parser logic.

## Risks

- The request text contains `Sispyhus`; this slice assumes the intended canonical spelling is `Sisyphus`.
- Showing `sisyphus` in help output while retaining the `taskflow` alias creates an intentional mixed state for compatibility.
- MCP setup docs must stay accurate until a real `sisyphus.mcp_server` module exists.

## Test Strategy

### Normal Cases

- [ ] CLI help surfaces `sisyphus` as the program name.
- [ ] Generated feature and issue plan text uses `sisyphus verify`.

### Edge Cases

- [ ] `taskflow` remains a working runtime alias even though the help and generated guidance prefer `sisyphus`.
- [ ] MCP docs remain technically accurate by describing `taskflow.mcp_server` as a compatibility path rather than renaming it prematurely.

### Exception Cases

- [ ] This slice does not accidentally rename high-risk identifiers such as `.taskflow.toml`, `taskflow.event.v1`, or `src/taskflow/`.
- [ ] No docs instruct users to run commands that do not exist in the current codebase.

## Verification Mapping

- `CLI help surfaces sisyphus as the program name.` -> `python -m unittest tests.test_taskflow -v`
- `Generated feature and issue plan text uses sisyphus verify.` -> `python -m unittest tests.test_taskflow -v`
- `taskflow remains a working runtime alias and MCP docs stay accurate.` -> `manual review of updated docs and unchanged compatibility entry points`
- `High-risk identifiers are not renamed accidentally.` -> `manual review of diff for config, event schema, and package paths`

## External LLM Review

- Required: `no`
- Provider: `n/a`
- Purpose: `n/a`
- Trigger: `n/a`
