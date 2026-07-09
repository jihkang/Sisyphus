from __future__ import annotations

DEFAULT_STALE_AFTER_SECONDS = 900
ACTIVE_AGENT_STATUSES = {"queued", "running", "waiting"}
FINAL_AGENT_STATUSES = {"completed", "failed", "cancelled"}
AGENT_STATUSES = ACTIVE_AGENT_STATUSES | FINAL_AGENT_STATUSES
