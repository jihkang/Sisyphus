from __future__ import annotations

import unittest

from sisyphus.application.metrics import build_value_metrics_report


class MetricsApplicationTests(unittest.TestCase):
    def test_report_is_a_deterministic_projection_of_tasks_events_and_clock(self) -> None:
        tasks = [
            {
                "id": "TF-1",
                "status": "open",
                "workflow_phase": "promotion_pending",
                "verify_status": "passed",
                "last_verified_at": "2026-07-19T12:01:00Z",
                "promotion": {
                    "required": True,
                    "strategy": "direct",
                    "recorded_at": "2026-07-19T12:06:00Z",
                },
            }
        ]
        entries = [
            {
                "event_id": "evt-1",
                "event_type": "conversation",
                "status": "queued",
                "timestamp": "2026-07-19T12:00:00Z",
            },
            {
                "event_id": "evt-1",
                "event_type": "conversation",
                "status": "processed",
                "timestamp": "2026-07-19T12:00:12Z",
            },
            {
                "event_type": "task.manual_intervention_required",
                "timestamp": "2026-07-19T12:02:00Z",
                "data": {"task_id": "TF-1", "reason": "promotion_required"},
            },
        ]

        report = build_value_metrics_report(
            tasks=tasks,
            entries=entries,
            event_log_paths=["/repo/.planning/events.jsonl"],
            generated_at="2026-07-19T13:00:00Z",
        )

        self.assertEqual(report["generated_at"], "2026-07-19T13:00:00Z")
        self.assertEqual(report["sources"]["event_log_paths"], ["/repo/.planning/events.jsonl"])
        self.assertEqual(
            report["metrics"]["session_resume_time"]["summary"]["average_seconds"],
            12.0,
        )
        self.assertEqual(report["metrics"]["promotion_lead_time"]["sample_count"], 1)
        self.assertEqual(report["metrics"]["manual_intervention_count"]["count"], 1)
        self.assertEqual(
            report["metrics"]["manual_intervention_count"]["pending_tasks"][0]["task_id"],
            "TF-1",
        )


if __name__ == "__main__":
    unittest.main()
