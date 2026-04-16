from __future__ import annotations

from taskflow.cli import (
    build_parser,
    handle_agent_finish,
    handle_agent_run,
    handle_agent_start,
    handle_agent_update,
    handle_agents,
    handle_close,
    handle_daemon,
    handle_discord_bot,
    handle_ingest_conversation,
    handle_new,
    handle_plan_approve,
    handle_plan_request_changes,
    handle_plan_revise,
    handle_request,
    handle_serve,
    handle_spec_freeze,
    handle_status,
    handle_subtasks_generate,
    handle_verify,
    main,
)

__all__ = [
    "build_parser",
    "handle_agent_finish",
    "handle_agent_run",
    "handle_agent_start",
    "handle_agent_update",
    "handle_agents",
    "handle_close",
    "handle_daemon",
    "handle_discord_bot",
    "handle_ingest_conversation",
    "handle_new",
    "handle_plan_approve",
    "handle_plan_request_changes",
    "handle_plan_revise",
    "handle_request",
    "handle_serve",
    "handle_spec_freeze",
    "handle_status",
    "handle_subtasks_generate",
    "handle_verify",
    "main",
]


if __name__ == "__main__":
    raise SystemExit(main())
