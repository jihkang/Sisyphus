from __future__ import annotations


def mcp_resource_definitions() -> list[dict[str, object]]:
    return [
        {"uri": "repo://status/tasks", "description": "Structured list of all tasks in the repository."},
        {"uri": "repo://status/conformance", "description": "Repository-wide task conformance board."},
        {"uri": "repo://status/board", "description": "Operator-focused board with conformance summary and recent events."},
        {"uri": "repo://status/events", "description": "Recent event bus envelopes from the repository event log."},
        {"uri": "repo://status/metrics", "description": "Repository-level workflow value metrics derived from task state and lifecycle events."},
        {"uri": "repo://search/status", "description": "Repo-local search index status and document count."},
        {"uri": "repo://schema/mcp", "description": "Human-readable MCP tool and resource schema for Sisyphus."},
        {"uri": "context://<context-pack-id>", "description": "Persisted ContextPack JSON built from repo-local search results."},
        {"uri": "evolution://<run-id>/run", "description": "Read-only overview for a persisted evolution run."},
        {"uri": "evolution://<run-id>/status", "description": "Read-only status summary for a persisted evolution run."},
        {"uri": "evolution://<run-id>/report", "description": "Read-only report for a persisted evolution run."},
        {"uri": "evolution://compare/<left-run-id>/<right-run-id>", "description": "Read-only comparison across two persisted evolution runs."},
        {"uri": "task://<task-id>/record", "description": "Raw task record JSON."},
        {"uri": "task://<task-id>/conformance", "description": "Task-level conformance summary."},
        {"uri": "task://<task-id>/timeline", "description": "Task and subtask conformance/drift timeline."},
        {"uri": "task://<task-id>/brief", "description": "Task brief markdown."},
        {"uri": "task://<task-id>/plan", "description": "Task plan markdown."},
        {"uri": "task://<task-id>/repro", "description": "Task repro markdown for issue tasks."},
        {"uri": "task://<task-id>/verify", "description": "Task verification markdown."},
        {"uri": "task://<task-id>/log", "description": "Task log markdown."},
        {"uri": "task://<task-id>/promotion", "description": "Recorded promotion receipt JSON for a merged pull request."},
        {"uri": "task://<task-id>/changeset", "description": "Human-readable merged pull request changeset markdown."},
        {"uri": "task://<task-id>/agents", "description": "Tracked agent records for a task."},
        {"uri": "task://<task-id>/artifact-graph", "description": "Read-only FeatureChangeArtifact graph projection for a feature task."},
        {"uri": "task://<task-id>/compiled-obligations", "description": "Compiled obligation queue derived from the feature task artifact projection."},
        {"uri": "task://<task-id>/slot-bindings", "description": "Projected slot bindings for a feature task artifact envelope."},
        {"uri": "task://<task-id>/verification-claims", "description": "Projected verification claims bound to a feature task artifact envelope."},
        {"uri": "task://<task-id>/promotion-summary", "description": "Read-only promotion decision summary derived from the feature task artifact projection."},
        {"uri": "task://<task-id>/invalidation-summary", "description": "Read-only invalidation summary derived from the feature task artifact projection."},
    ]


__all__ = [
    "mcp_resource_definitions",
]
