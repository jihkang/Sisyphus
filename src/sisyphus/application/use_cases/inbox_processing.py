from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path

from ...domain.inbox import InboxValidationError
from ..ports.clock import ClockPort
from ..ports.inbox import (
    InboxEventHandler,
    InboxEventLogPort,
    InboxEventParser,
    InboxRecord,
    InboxRepositoryPort,
)
from ..ports.workflow import EventPublisherPort, WorkflowEvent
from ..results.inbox import DaemonStats
from .inbox import DaemonError


@dataclass(slots=True)
class InboxProcessingService:
    inbox: InboxRepositoryPort
    parse_event: InboxEventParser
    handlers: dict[str, InboxEventHandler]
    event_log: InboxEventLogPort
    events: EventPublisherPort
    clock: ClockPort

    def process(
        self,
        event_path: Path,
        *,
        stats: DaemonStats | None = None,
    ) -> InboxRecord:
        claimed_path = self.inbox.claim(event_path)
        raw_event: object = None
        try:
            raw_event = self.inbox.read(claimed_path)
            event = self.parse_event(raw_event)
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            return self._quarantine_invalid(
                event_path=claimed_path,
                raw_event=raw_event,
                kind="invalid_json",
                error=exc,
                stats=stats,
            )
        except InboxValidationError as exc:
            kind = (
                "unsupported_event_type"
                if exc.code == "unsupported_event_type"
                else "invalid_schema"
            )
            return self._quarantine_invalid(
                event_path=claimed_path,
                raw_event=raw_event,
                kind=kind,
                error=exc,
                stats=stats,
            )

        event["status"] = "processing"
        event["updated_at"] = self.clock.now()
        self.inbox.update(claimed_path, event)

        try:
            self.event_log.append(
                {
                    "timestamp": self.clock.now(),
                    "event_id": event.get("id"),
                    "event_type": event.get("event_type"),
                    "status": "processing",
                    "message": f"processing {claimed_path.name}",
                }
            )
            event_type = str(event.get("event_type"))
            handler = self.handlers.get(event_type)
            if handler is None:
                raise DaemonError(f"unsupported event type: {event.get('event_type')}")
            result = handler(event)
            event["status"] = "processed"
            event["updated_at"] = self.clock.now()
            event["result"] = result
            event["error"] = None
            success_message = (
                f"created task {result['task_id']}"
                if event_type == "conversation"
                else f"recorded merge receipt for task {result['task_id']}"
            )
            self.event_log.append(
                {
                    "timestamp": self.clock.now(),
                    "event_id": event.get("id"),
                    "event_type": event.get("event_type"),
                    "status": "processed",
                    "message": success_message,
                    "result": result,
                }
            )
            processed_type = (
                "conversation.processed"
                if event_type == "conversation"
                else "pull_request.merged.processed"
            )
            processed_data: dict[str, object] = {
                "event_id": event.get("id"),
                "task_id": result.get("task_id"),
                "status": "processed",
            }
            if event_type == "pull_request_merged":
                processed_data["pr_number"] = result.get("pr_number")
            self.events.publish(
                WorkflowEvent(
                    event_type=processed_type,
                    source={"module": "daemon"},
                    data=processed_data,
                )
            )
            self.inbox.complete(claimed_path, event)
            if stats is not None:
                stats.processed += 1
            return event
        except Exception as exc:
            return self._fail(
                event_path=claimed_path,
                event=event,
                error=str(exc),
                stats=stats,
            )

    def _quarantine_invalid(
        self,
        *,
        event_path: Path,
        raw_event: object,
        kind: str,
        error: Exception,
        stats: DaemonStats | None,
    ) -> InboxRecord:
        error_text = f"{kind}: {error}"
        event = self._normalized_failed_event(
            raw_event,
            event_path=event_path,
            error=error_text,
        )
        return self._fail(
            event_path=event_path,
            event=event,
            error=error_text,
            stats=stats,
        )

    def _normalized_failed_event(
        self,
        raw_event: object,
        *,
        event_path: Path,
        error: str,
    ) -> InboxRecord:
        data = raw_event if type(raw_event) is dict else {}
        event_id = data.get("id") if type(data.get("id")) is str else event_path.stem
        event_type = (
            data.get("event_type")
            if type(data.get("event_type")) is str
            else "unknown"
        )
        created_at = (
            data.get("created_at")
            if type(data.get("created_at")) is str
            else self.clock.now()
        )
        return {
            "id": str(event_id)[:128] or event_path.stem[:128] or "unknown",
            "event_type": str(event_type)[:64] or "unknown",
            "status": "failed",
            "created_at": str(created_at)[:128] or self.clock.now(),
            "updated_at": self.clock.now(),
            "payload": {},
            "result": None,
            "error": error[:4096],
        }

    def _fail(
        self,
        *,
        event_path: Path,
        event: InboxRecord,
        error: str,
        stats: DaemonStats | None,
    ) -> InboxRecord:
        error = error[:4096]
        event["status"] = "failed"
        event["updated_at"] = self.clock.now()
        event["error"] = error
        self.inbox.fail(event_path, event)
        if stats is not None:
            stats.failed += 1
        self._report_failure(event=event, error=error)
        return event

    def _report_failure(self, *, event: InboxRecord, error: str) -> None:
        try:
            self.event_log.append(
                {
                    "timestamp": self.clock.now(),
                    "event_id": event.get("id"),
                    "event_type": event.get("event_type"),
                    "status": "failed",
                    "message": error,
                }
            )
        except Exception:
            pass

        failed_type = {
            "conversation": "conversation.failed",
            "pull_request_merged": "pull_request.merged.failed",
        }.get(str(event.get("event_type") or "unknown"), "inbox.event.failed")
        try:
            self.events.publish(
                WorkflowEvent(
                    event_type=failed_type,
                    source={"module": "daemon"},
                    data={
                        "event_id": event.get("id"),
                        "status": "failed",
                        "error": error,
                    },
                )
            )
        except Exception:
            pass


__all__ = ["InboxProcessingService"]
