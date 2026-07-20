# External Review Evidence

Last verified against code: 2026-07-20

Sisyphus treats a required external LLM review as immutable evidence, not as a
caller-supplied verdict. The reviewer produces a Markdown report and a strict
JSON envelope. Sisyphus derives pass or fail from the envelope findings, binds
the evidence to the exact Git revision and frozen task scope, and requires a
new verification run before promotion.

## Review Scope

Generate the canonical review inputs after the implementation is committed and
the worktree contains no unrelated changes:

```bash
sisyphus review scope <task-id> --json
```

The result contains:

- `current_head_sha`: the exact Git revision to review
- `scope_digest`: SHA-256 over the task identity, branch and base, frozen plan
  and design policy, verification profile and commands, test strategy,
  promotion policy, owned paths, and authority-document digests
- `document_digests`: the BRIEF, PLAN or issue documents, frozen design
  artifacts, and spec-validation report used by the scope digest

Any change to the reviewed Git HEAD or canonical scope makes the review stale.

## Artifact Location

Both files must be regular, non-symlink files directly under:

```text
.planning/tasks/<task-id>/artifacts/reviews/
```

The report must use the `.md` suffix and is limited to 1 MiB. The envelope must
use `.json` and is limited to 256 KiB. Descriptor-relative no-follow reads
enforce repository containment.

## Envelope Contract

The envelope schema is exact. Missing, unknown, or duplicate JSON keys are
rejected.

```json
{
  "schema_version": "sisyphus.external_review.v1",
  "provider": "independent Codex reviewer",
  "reviewer": "reviewer-agent-id",
  "reviewed_head_sha": "0123456789abcdef0123456789abcdef01234567",
  "scope_digest": "sha256:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
  "report": {
    "path": ".planning/tasks/<task-id>/artifacts/reviews/review.md",
    "digest": "sha256:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
  },
  "summary": "No blocking findings.",
  "findings": []
}
```

Each finding has exactly these fields:

```json
{
  "id": "P1-1",
  "severity": "P1",
  "title": "Verification bypass",
  "detail": "The reviewed revision permits a verification bypass.",
  "blocking": true
}
```

Supported severities are `P0` through `P3`. `P0` and `P1` findings must be
blocking. Any blocking finding derives a failed review; no caller-provided
status or count is accepted.

## Recording And Verification

Record the envelope through the application boundary:

```bash
sisyphus review record <task-id> \
  --envelope .planning/tasks/<task-id>/artifacts/reviews/review.json \
  --json
```

Recording performs two complete evidence inspections around the atomic task
update. A change to the report, envelope, HEAD, scope documents, worktree, or
review policy aborts the transition. A successful record still invalidates any
older verification result and marks promotion as requiring re-verification.

`sisyphus verify <task-id>` then checks the evidence before and after all verify
commands. A pass stores a binding over the envelope digest, report digest,
reviewed HEAD, and scope digest. Close and promotion reject a missing or stale
binding.

Before promotion, Sisyphus inspects the envelope, report, HEAD, scope, and dirty
paths again. For a review-gated task it never stages new work: only the two
review files, `task.json`, `VERIFY.md`, and the verification evidence graph may
remain as exact service-generated local artifacts. The promotion pushes the
already-reviewed commit SHA itself. Any other workspace change requires a new
review and verification cycle. This avoids creating an unreviewed commit merely
to carry the review that names its own reviewed HEAD.

## MCP Authorization

The MCP recording tool is an operator write boundary. Configure a non-empty
capability in the MCP server environment:

```bash
export SISYPHUS_OPERATOR_CAPABILITY='<secret>'
```

Call `sisyphus.record_external_review` with the same value in the write-only
`operator_capability` field. The capability is constant-time compared and is
never persisted in an episode trace; the trace renderer also redacts the field
defensively. Scope inspection is read-only and does not require this capability.

The local CLI remains an operator surface and does not use the MCP capability.
