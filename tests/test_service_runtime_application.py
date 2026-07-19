from __future__ import annotations

import unittest

from sisyphus.application.results.inbox import DaemonStats
from sisyphus.application.results.service_runtime import TaskNotification
from sisyphus.application.use_cases.service_runtime import ServiceRuntime


class TrackerFake:
    def __init__(self, notifications: list[TaskNotification] | None = None) -> None:
        self.tasks: list[list[dict]] = []
        self.notifications = notifications or []

    def collect(self, tasks: list[dict]) -> list[TaskNotification]:
        self.tasks.append(tasks)
        notifications = list(self.notifications)
        self.notifications = []
        return notifications


class StopServiceLoop(RuntimeError):
    pass


class ServiceRuntimeTests(unittest.TestCase):
    def test_step_runs_daemon_and_sorts_tasks_before_tracking(self) -> None:
        daemon_calls: list[int | None] = []
        tracker = TrackerFake()
        runtime = ServiceRuntime(
            daemon_step=lambda max_events: (
                daemon_calls.append(max_events) or DaemonStats(processed=1)
            ),
            list_tasks=lambda: [
                {"id": "TF-2", "updated_at": "2026-07-19T12:02:00Z"},
                {"id": "TF-1", "updated_at": "2026-07-19T12:01:00Z"},
            ],
            sleep=lambda _: None,
        )

        result = runtime.step(tracker=tracker, max_events=3)

        self.assertEqual(daemon_calls, [3])
        self.assertEqual(result.stats.processed, 1)
        self.assertTrue(result.progressed)
        self.assertEqual(
            [task["id"] for task in tracker.tasks[0]],
            ["TF-1", "TF-2"],
        )

    def test_step_does_not_query_tasks_without_a_tracker(self) -> None:
        runtime = ServiceRuntime(
            daemon_step=lambda _: DaemonStats(),
            list_tasks=lambda: self.fail("task query must not run without a tracker"),
            sleep=lambda _: None,
        )

        result = runtime.step()

        self.assertFalse(result.progressed)
        self.assertEqual(result.notifications, [])

    def test_run_delivers_notifications_and_sleeps_when_idle(self) -> None:
        notification = TaskNotification(
            task_id="TF-1",
            summary="updated",
            source_context={"kind": "discord"},
        )
        tracker = TrackerFake([notification])
        delivered: list[TaskNotification] = []
        sleep_calls: list[float] = []

        def stop_after_sleep(seconds: float) -> None:
            sleep_calls.append(seconds)
            raise StopServiceLoop

        runtime = ServiceRuntime(
            daemon_step=lambda _: DaemonStats(),
            list_tasks=lambda: [{"id": "TF-1", "updated_at": "2026-07-19T12:00:00Z"}],
            sleep=stop_after_sleep,
        )

        with self.assertRaises(StopServiceLoop):
            runtime.run(
                poll_interval_seconds=0,
                tracker=tracker,
                notifier=delivered.append,
            )

        self.assertEqual(delivered, [notification])
        self.assertEqual(sleep_calls, [1])


if __name__ == "__main__":
    unittest.main()
