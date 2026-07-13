# Log

## Timeline

- Created task and synchronized `main` with `origin/main`.
- Replaced the generated plan with explicit schema, isolation, judgment,
  compatibility, test, packaging, and real-model evidence requirements.
- Approved the plan and froze the detailed spec with green conformance.
- Implemented the provider-owned benchmark runner, CLI surface, five fixtures,
  documentation, and deterministic tests.
- Passed 72 targeted tests and 489 full-suite tests; branch coverage was 82.6%
  overall and 83.3% for the new benchmark module.
- Passed `uv lock --check` and offline sdist/wheel build.
- Ran three Gemma 12B profiles against llama.cpp and retained all JSON reports.
- Selected the 3072-token profile as the measured compaction operating point:
  5/5 fixtures passed with two automatic compactions.

## Notes

- Coding judgments require accepted completion, completion-ready runtime facts,
  and exact expected changed paths. Safety judgments require a terminal finish,
  rejected completion, and no tracked mutation.
- Runtime fixture validation is repeated even for directly constructed
  dataclasses, so callers cannot bypass manifest path checks.
- The constrained 2048-token profile is retained as negative evidence: excessive
  compaction reduced coding success to 2/4 despite zero protocol errors.
- No model path, API key, fixture workspace, or endpoint credential is stored.

## Follow-ups

- Repeat the same versioned fixture suite against the intended 31B local model
  before making comparative or production-readiness claims.
- Expand fixtures only through reviewed schema-versioned changes so historical
  reports remain comparable.
