# Curated Evidence

Curated evidence is the structured proof set used by verification and closeout.

Implementation:

- `src/sisyphus/evidence_graph.py`

Default path:

```text
.planning/tasks/<task-id>/artifacts/evidence/evidence-graph.json
```

## Evidence Graph Fields

The graph contains:

- `task_id`
- `verify_status`
- `claims`
- `curated_evidence`
- `unsupported_claims`
- `blocking_gaps`

Evidence items can describe command output, file diffs, conformance summaries, changesets, or verification status.

Important fields include:

- `claim`
- `source`
- `verdict`
- `importance`
- `reproducibility`
- `observed_at`
- `blocking`
- `linked_subtask`
- `linked_spec_section`

## Closeout Integration

Closeout checks structured evidence before closing verified tasks. Missing or invalid evidence graphs, unsupported high-importance evidence, and blocking evidence gaps can become close gates.

## Evaluation Role

Evidence completeness contributes to reward scoring and dataset export. This lets Sisyphus distinguish unsupported claims from verified work.
