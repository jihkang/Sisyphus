from __future__ import annotations

from pathlib import Path
import unittest

from sisyphus.application.episode_trace import EpisodeStep
from sisyphus.application.use_cases.episode_trace import EpisodeTraceService


class FakeEpisodeTraceStore:
    def __init__(self) -> None:
        self.appended: list[EpisodeStep] = []
        self.next_calls: list[str] = []
        self.steps: list[dict[str, object]] = []

    def append(self, episode_step: EpisodeStep) -> Path:
        self.appended.append(episode_step)
        return Path(f"/task/artifacts/episodes/{episode_step.episode_id}.jsonl")

    def next_step(self, episode_id: str) -> int:
        self.next_calls.append(episode_id)
        return 3

    def read(self, *, episode_id: str | None = None) -> list[dict[str, object]]:
        return list(self.steps)


class FixedClock:
    def now(self) -> str:
        return "2026-07-19T14:00:00Z"


class EpisodeTraceServiceTests(unittest.TestCase):
    def test_record_resolves_next_step_and_appends_one_timestamped_record(self) -> None:
        store = FakeEpisodeTraceStore()
        service = EpisodeTraceService(store=store, clock=FixedClock())

        step, path = service.record(
            episode_id="ep-TF-1-worker",
            task_id="TF-1",
            observation={"observation_hash": "sha256:before"},
            action_name="sisyphus.verify_task",
            arguments={"task_id": "TF-1"},
            result={"status": "passed"},
            state_before={"verify_status": "not_run"},
            state_after={"verify_status": "passed"},
            actor={"agent_id": "worker"},
        )

        self.assertEqual(store.next_calls, ["ep-TF-1-worker"])
        self.assertEqual(store.appended, [step])
        self.assertEqual(step.step, 3)
        self.assertEqual(step.timestamp, "2026-07-19T14:00:00Z")
        self.assertEqual(step.state_diff["verify_status"], ["not_run", "passed"])
        self.assertEqual(path.name, "ep-TF-1-worker.jsonl")

    def test_explicit_step_avoids_repeated_trace_scan(self) -> None:
        store = FakeEpisodeTraceStore()
        service = EpisodeTraceService(store=store, clock=FixedClock())

        step, _ = service.record(
            episode_id="ep-TF-1-worker",
            task_id="TF-1",
            step=7,
            observation={"observation_hash": "sha256:before"},
            action_name="local_agent.test",
            arguments={},
            result={},
            state_before={},
            state_after={},
        )

        self.assertEqual(step.step, 7)
        self.assertEqual(store.next_calls, [])


if __name__ == "__main__":
    unittest.main()
