from __future__ import annotations


def mcp_tool_definitions() -> list[dict[str, object]]:
    return [
        {
            "name": "sisyphus.request_task",
            "description": "Create a repository-local task from a natural-language request.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "message": {"type": "string"},
                    "title": {"type": "string"},
                    "task_type": {"type": "string", "enum": ["feature", "issue"]},
                    "slug": {"type": "string"},
                    "instruction": {"type": "string"},
                    "agent_id": {"type": "string"},
                    "role": {"type": "string"},
                    "provider": {"type": "string"},
                    "owned_paths": {"type": "array", "items": {"type": "string"}},
                    "provider_args": {"type": "array", "items": {"type": "string"}},
                    "auto_run": {"type": "boolean"},
                },
                "required": ["message"],
                "additionalProperties": False,
            },
            "outputSchema": {
                "type": "object",
                "properties": {
                    "ok": {"type": "boolean"},
                    "event_id": {"type": ["string", "null"]},
                    "task_id": {"type": ["string", "null"]},
                    "event_status": {"type": ["string", "null"]},
                    "orchestrated": {"type": "integer"},
                    "error": {"type": ["string", "null"]},
                },
            },
        },
        {
            "name": "sisyphus.list_tasks",
            "description": "List repository tasks.",
            "inputSchema": {
                "type": "object",
                "properties": {},
                "additionalProperties": False,
            },
            "outputSchema": {"type": "object", "properties": {"tasks": {"type": "array"}}},
        },
        {
            "name": "sisyphus.get_task",
            "description": "Read a single task record.",
            "inputSchema": {
                "type": "object",
                "properties": {"task_id": {"type": "string"}},
                "required": ["task_id"],
                "additionalProperties": False,
            },
            "outputSchema": {"type": "object", "properties": {"task": {"type": "object"}}},
        },
        {
            "name": "sisyphus.search_index_rebuild",
            "description": "Rebuild the repo-local SearchDocument JSONL index from task docs and artifact evidence.",
            "inputSchema": {
                "type": "object",
                "properties": {},
                "additionalProperties": False,
            },
            "outputSchema": {
                "type": "object",
                "properties": {
                    "index_path": {"type": "string"},
                    "document_count": {"type": "integer"},
                    "changed": {"type": "boolean"},
                },
            },
        },
        {
            "name": "sisyphus.search",
            "description": "Search the repo-local SearchDocument index for task spec and artifact evidence.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "limit": {"type": "integer", "minimum": 1},
                    "rebuild_if_missing": {"type": "boolean"},
                },
                "required": ["query"],
                "additionalProperties": False,
            },
            "outputSchema": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "result_count": {"type": "integer"},
                    "results": {"type": "array"},
                },
            },
        },
        {
            "name": "sisyphus.context_build",
            "description": "Build and persist a ContextPack from repo-local search results.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "limit": {"type": "integer", "minimum": 1},
                    "max_excerpt_chars": {"type": "integer", "minimum": 80},
                    "rebuild_if_missing": {"type": "boolean"},
                },
                "required": ["query"],
                "additionalProperties": False,
            },
            "outputSchema": {
                "type": "object",
                "properties": {
                    "pack_path": {"type": "string"},
                    "context_pack": {"type": "object"},
                },
            },
        },
        {
            "name": "sisyphus.evolution_execute",
            "description": "Start a new read-only evolution run and return reviewable run metadata.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "run_id": {"type": "string"},
                    "target_ids": {"type": "array", "items": {"type": "string"}},
                    "task_ids": {"type": "array", "items": {"type": "string"}},
                    "max_events": {"type": "integer"},
                },
                "additionalProperties": False,
            },
            "outputSchema": {
                "type": "object",
                "properties": {
                    "ok": {"type": "boolean"},
                    "run_id": {"type": ["string", "null"]},
                    "resource_uri": {"type": ["string", "null"]},
                    "artifact_dir": {"type": ["string", "null"]},
                    "final_stage": {"type": ["string", "null"]},
                    "failure_stage": {"type": ["string", "null"]},
                    "content": {"type": "string"},
                    "error": {"type": ["string", "null"]},
                    "error_type": {"type": ["string", "null"]},
                },
            },
        },
        {
            "name": "sisyphus.evolution_followup_request",
            "description": "Create a review-gated Sisyphus follow-up task from an evolution run.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "run_id": {"type": "string"},
                    "candidate_id": {"type": "string"},
                    "title": {"type": "string"},
                    "summary": {"type": "string"},
                    "requested_task_type": {"type": "string", "enum": ["feature", "issue"]},
                    "slug": {"type": "string"},
                    "target_ids": {"type": "array", "items": {"type": "string"}},
                    "owned_paths": {"type": "array", "items": {"type": "string"}},
                    "review_gates": {"type": "array", "items": {"type": "string"}},
                    "verification_obligations": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "claim": {"type": "string"},
                                "method": {"type": "string"},
                                "required": {"type": "boolean"},
                            },
                            "required": ["claim", "method"],
                            "additionalProperties": False,
                        },
                    },
                    "evidence_summary": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "kind": {"type": "string"},
                                "summary": {"type": "string"},
                                "locator": {"type": "string"},
                            },
                            "required": ["kind", "summary"],
                            "additionalProperties": False,
                        },
                    },
                },
                "required": ["run_id", "candidate_id", "title", "summary"],
                "additionalProperties": False,
            },
            "outputSchema": {
                "type": "object",
                "properties": {
                    "task_id": {"type": "string"},
                    "task_uri": {"type": "string"},
                    "run_id": {"type": "string"},
                    "candidate_id": {"type": "string"},
                    "requested_targets": {"type": "array", "items": {"type": "string"}},
                    "required_review_gates": {"type": "array", "items": {"type": "string"}},
                    "content": {"type": "string"},
                },
            },
        },
        {
            "name": "sisyphus.evolution_decide",
            "description": "Evaluate an evolution follow-up task and record the current promotion or invalidation decision.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "task_id": {"type": "string"},
                    "claim": {"type": "string"},
                },
                "required": ["task_id"],
                "additionalProperties": False,
            },
            "outputSchema": {
                "type": "object",
                "properties": {
                    "task_id": {"type": "string"},
                    "task_uri": {"type": "string"},
                    "run_id": {"type": "string"},
                    "candidate_id": {"type": "string"},
                    "gate_status": {"type": "string"},
                    "envelope_status": {"type": "string"},
                    "content": {"type": "string"},
                },
            },
        },
        {
            "name": "sisyphus.evolution_run",
            "description": "Render the read-only overview for a persisted evolution run.",
            "inputSchema": {
                "type": "object",
                "properties": {"run_id": {"type": "string"}},
                "required": ["run_id"],
                "additionalProperties": False,
            },
            "outputSchema": {
                "type": "object",
                "properties": {
                    "run_id": {"type": "string"},
                    "resource_uri": {"type": "string"},
                    "content": {"type": "string"},
                },
            },
        },
        {
            "name": "sisyphus.evolution_status",
            "description": "Render the read-only status summary for a persisted evolution run.",
            "inputSchema": {
                "type": "object",
                "properties": {"run_id": {"type": "string"}},
                "required": ["run_id"],
                "additionalProperties": False,
            },
            "outputSchema": {
                "type": "object",
                "properties": {
                    "run_id": {"type": "string"},
                    "resource_uri": {"type": "string"},
                    "content": {"type": "string"},
                },
            },
        },
        {
            "name": "sisyphus.evolution_report",
            "description": "Render the read-only report for a persisted evolution run.",
            "inputSchema": {
                "type": "object",
                "properties": {"run_id": {"type": "string"}},
                "required": ["run_id"],
                "additionalProperties": False,
            },
            "outputSchema": {
                "type": "object",
                "properties": {
                    "run_id": {"type": "string"},
                    "resource_uri": {"type": "string"},
                    "content": {"type": "string"},
                },
            },
        },
        {
            "name": "sisyphus.evolution_compare",
            "description": "Render a read-only comparison across two persisted evolution runs.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "left_run_id": {"type": "string"},
                    "right_run_id": {"type": "string"},
                },
                "required": ["left_run_id", "right_run_id"],
                "additionalProperties": False,
            },
            "outputSchema": {
                "type": "object",
                "properties": {
                    "left_run_id": {"type": "string"},
                    "right_run_id": {"type": "string"},
                    "resource_uri": {"type": "string"},
                    "content": {"type": "string"},
                },
            },
        },
        {
            "name": "sisyphus.record_merged_pr",
            "description": "Record a merged pull request as a promotion receipt and project a changeset summary.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "task_id": {"type": "string"},
                    "branch": {"type": "string"},
                    "repo_full_name": {"type": "string"},
                    "pr_number": {"type": "integer", "minimum": 1},
                    "title": {"type": "string"},
                    "url": {"type": "string"},
                    "base_branch": {"type": "string"},
                    "head_branch": {"type": "string"},
                    "head_sha": {"type": "string"},
                    "merge_commit_sha": {"type": "string"},
                    "merged_at": {"type": "string"},
                    "merged_by": {"type": "string"},
                    "merge_method": {"type": "string"},
                    "additions": {"type": "integer"},
                    "deletions": {"type": "integer"},
                    "changed_files": {"type": "array", "items": {"type": "object"}},
                },
                "required": ["pr_number", "title"],
                "additionalProperties": False,
            },
            "outputSchema": {
                "type": "object",
                "properties": {
                    "ok": {"type": "boolean"},
                    "event_id": {"type": ["string", "null"]},
                    "event_status": {"type": "string"},
                    "task_id": {"type": ["string", "null"]},
                    "pr_number": {"type": ["integer", "null"]},
                    "receipt_path": {"type": ["string", "null"]},
                    "changeset_path": {"type": ["string", "null"]},
                    "close_attempted": {"type": "boolean"},
                    "closed": {"type": "boolean"},
                    "close_status": {"type": ["string", "null"]},
                    "close_gate_codes": {"type": "array", "items": {"type": "string"}},
                    "child_retargeted_task_ids": {"type": "array", "items": {"type": "string"}},
                    "error": {"type": ["string", "null"]},
                },
            },
        },
        {
            "name": "sisyphus.execute_promotion",
            "description": "Commit, push, and open a pull request for a promotable task branch.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "task_id": {"type": "string"},
                    "remote_name": {"type": "string"},
                    "repo_full_name": {"type": "string"},
                    "title": {"type": "string"},
                    "body": {"type": "string"},
                    "commit_message": {"type": "string"},
                    "base_branch": {"type": "string"},
                    "head_branch": {"type": "string"},
                    "draft": {"type": "boolean"},
                },
                "required": ["task_id"],
                "additionalProperties": False,
            },
            "outputSchema": {
                "type": "object",
                "properties": {
                    "ok": {"type": "boolean"},
                    "task_id": {"type": ["string", "null"]},
                    "status": {"type": ["string", "null"]},
                    "branch": {"type": ["string", "null"]},
                    "base_branch": {"type": ["string", "null"]},
                    "head_branch": {"type": ["string", "null"]},
                    "commit_sha": {"type": ["string", "null"]},
                    "pr_number": {"type": ["integer", "null"]},
                    "pr_url": {"type": ["string", "null"]},
                    "receipt_path": {"type": ["string", "null"]},
                    "error": {"type": ["string", "null"]},
                },
            },
        },
        {
            "name": "sisyphus.plan_approve",
            "description": "Approve a task plan.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "task_id": {"type": "string"},
                    "reviewer": {"type": "string"},
                    "notes": {"type": "string"},
                },
                "required": ["task_id"],
                "additionalProperties": False,
            },
            "outputSchema": {"type": "object", "properties": {"task_id": {"type": "string"}, "plan_status": {"type": "string"}, "task_status": {"type": "string"}, "gates": {"type": "array"}}},
        },
        {
            "name": "sisyphus.plan_request_changes",
            "description": "Request plan changes for a task.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "task_id": {"type": "string"},
                    "reviewer": {"type": "string"},
                    "notes": {"type": "string"},
                },
                "required": ["task_id"],
                "additionalProperties": False,
            },
            "outputSchema": {"type": "object", "properties": {"task_id": {"type": "string"}, "plan_status": {"type": "string"}, "task_status": {"type": "string"}, "gates": {"type": "array"}}},
        },
        {
            "name": "sisyphus.plan_revise",
            "description": "Revise a task plan after review.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "task_id": {"type": "string"},
                    "author": {"type": "string"},
                    "notes": {"type": "string"},
                },
                "required": ["task_id"],
                "additionalProperties": False,
            },
            "outputSchema": {"type": "object", "properties": {"task_id": {"type": "string"}, "plan_status": {"type": "string"}, "task_status": {"type": "string"}, "gates": {"type": "array"}}},
        },
        {
            "name": "sisyphus.spec_freeze",
            "description": "Freeze a task spec.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "task_id": {"type": "string"},
                    "reviewer": {"type": "string"},
                    "notes": {"type": "string"},
                },
                "required": ["task_id"],
                "additionalProperties": False,
            },
            "outputSchema": {"type": "object", "properties": {"task_id": {"type": "string"}, "spec_status": {"type": "string"}, "task_status": {"type": "string"}, "workflow_phase": {"type": "string"}}},
        },
        {
            "name": "sisyphus.spec_validate",
            "description": "Validate a task spec and persist a deterministic report.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "task_id": {"type": "string"},
                    "persist": {"type": "boolean"},
                },
                "required": ["task_id"],
                "additionalProperties": False,
            },
            "outputSchema": {
                "type": "object",
                "properties": {
                    "task_id": {"type": "string"},
                    "status": {"type": "string"},
                    "stale": {"type": "boolean"},
                    "report_path": {"type": "string"},
                    "gates": {"type": "array"},
                    "report": {"type": "object"},
                },
            },
        },
        {
            "name": "sisyphus.subtasks_generate",
            "description": "Generate subtasks from the current strategy.",
            "inputSchema": {
                "type": "object",
                "properties": {"task_id": {"type": "string"}},
                "required": ["task_id"],
                "additionalProperties": False,
            },
            "outputSchema": {"type": "object", "properties": {"task_id": {"type": "string"}, "workflow_phase": {"type": "string"}, "subtasks": {"type": "array"}}},
        },
        {
            "name": "sisyphus.record_external_review",
            "description": "Record independently produced external LLM review evidence.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "task_id": {"type": "string"},
                    "reviewer": {"type": "string"},
                    "verdict": {"type": "string", "enum": ["pass", "fail"]},
                    "report_path": {"type": "string"},
                    "reviewed_head_sha": {"type": "string"},
                    "finding_count": {"type": "integer", "minimum": 0},
                    "blocking_finding_count": {"type": "integer", "minimum": 0},
                    "summary": {"type": "string"},
                },
                "required": [
                    "task_id",
                    "reviewer",
                    "verdict",
                    "report_path",
                    "reviewed_head_sha",
                ],
                "additionalProperties": False,
            },
            "outputSchema": {
                "type": "object",
                "properties": {
                    "task_id": {"type": "string"},
                    "status": {"type": "string"},
                    "provider": {"type": "string"},
                    "reviewer": {"type": "string"},
                    "reviewed_head_sha": {"type": "string"},
                    "report_path": {"type": "string"},
                    "report_digest": {"type": "string"},
                    "finding_count": {"type": "integer"},
                    "blocking_finding_count": {"type": "integer"},
                    "completed_at": {"type": "string"},
                },
            },
        },
        {
            "name": "sisyphus.verify_task",
            "description": "Run verification for a task.",
            "inputSchema": {
                "type": "object",
                "properties": {"task_id": {"type": "string"}},
                "required": ["task_id"],
                "additionalProperties": False,
            },
            "outputSchema": {"type": "object", "properties": {"task_id": {"type": "string"}, "status": {"type": "string"}, "stage": {"type": "string"}, "gates": {"type": "array"}, "audit_attempts": {"type": "integer"}}},
        },
        {
            "name": "sisyphus.close_task",
            "description": "Close a verified task.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "task_id": {"type": "string"},
                    "allow_dirty": {"type": "boolean"},
                },
                "required": ["task_id"],
                "additionalProperties": False,
            },
            "outputSchema": {"type": "object", "properties": {"task_id": {"type": "string"}, "status": {"type": "string"}, "closed": {"type": "boolean"}, "allow_dirty": {"type": "boolean"}, "gates": {"type": "array"}}},
        },
        {
            "name": "sisyphus.list_agents",
            "description": "List tracked agents for the repo or a task.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "task_id": {"type": "string"},
                    "stale_after_seconds": {"type": "integer", "minimum": 1},
                },
                "additionalProperties": False,
            },
            "outputSchema": {"type": "object", "properties": {"agents": {"type": "array"}}},
        },
        {
            "name": "sisyphus.daemon_once",
            "description": "Process inbox events and run one daemon cycle.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "poll_interval_seconds": {"type": "integer", "minimum": 1},
                    "max_events": {"type": "integer", "minimum": 1},
                },
                "additionalProperties": False,
            },
            "outputSchema": {"type": "object", "properties": {"processed": {"type": "integer"}, "failed": {"type": "integer"}, "skipped": {"type": "integer"}, "orchestrated": {"type": "integer"}}},
        },
    ]


__all__ = [
    "mcp_tool_definitions",
]
