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
  and design policy, complete task-document mapping, verification profile and
  commands, test strategy, promotion policy, exact service-generated output
  paths, owned paths, authority-document digests, the immutable live-remote base
  commit, and a digest of the exact configured remote URL
- `document_digests`: the BRIEF, PLAN or issue documents, frozen design
  artifacts, and spec-validation report used by the scope digest

When a remote is configured, base resolution uses a bounded, non-interactive
live query and fails closed instead of accepting a stale local tracking ref.
Any change to the reviewed Git HEAD, remote identity, integration-base revision,
or canonical scope makes the review stale.

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

Recording also stores the exact task-relative paths that verification and
promotion are allowed to generate. They are derived from the reviewed task, not
accepted from the caller. Output paths must be distinct, normalized, contained,
and unchanged from the reviewed scope. They cannot equal, contain, or be nested
under `task.json`, non-verification task documents, frozen design artifacts, the
spec-validation report, or the review-artifact directory.

`sisyphus verify <task-id>` checks the evidence before commands, writes only the
recorded verification outputs, and then reloads the latest task under the
repository update lock. It compares the latest verification authority with the
pre-command snapshot and re-inspects the envelope, report, HEAD, scope, and dirty
paths before committing a pass. A final inspection runs after generated outputs
and task support files are synchronized. Concurrent authority and gate changes
are preserved and turn the attempt into a failed verification instead of being
overwritten. A pass stores a binding over the envelope digest, report digest,
reviewed HEAD, and scope digest.

Close and promotion independently re-inspect the envelope, report, HEAD, scope,
and exact dirty paths; `allow_dirty` never bypasses this review check. For a
review-gated task promotion never stages new work. Only the two review files,
`task.json`, the recorded verification outputs, and the recorded promotion
receipt may remain as service-generated artifacts. Promotion pushes the exact
reviewed commit SHA and rejects caller redirection to a different repository.
If PR creation fails after that push, the durable pushed
state allows a retry to discover the already-open head/base PR without creating
a duplicate. A failed final receipt write is repaired from durable PR state on
the next attempt. Promotion-state saves after external effects remain in the
control repository and do not mirror into the source worktree. Retry recovery
uses the actual workspace HEAD after a commit-state save failure and excludes
only exact task-state and receipt outputs from new source work. A newly created
commit is always pushed even when the attempt started from a previously pushed
state.
Any other workspace change requires a new review and verification cycle.

Closeout distinguishes a dirty worktree from an unavailable Git inspection.
The former can use the explicit dirty override; the latter records
`WORKTREE_STATUS_UNAVAILABLE` and cannot be bypassed by that override.

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
