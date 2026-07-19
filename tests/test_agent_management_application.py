from __future__ import annotations

from pathlib import Path
import sys
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))


from sisyphus.application.commands.agent import (  # noqa: E402
    RegisterAgentCommand,
    UpdateAgentCommand,
)
from sisyphus.application.use_cases.agents import (  # noqa: E402
    AgentManagementError,
    AgentManagementService,
)
from sisyphus.domain.agent import Agent  # noqa: E402
from sisyphus.domain.task.models import Task  # noqa: E402


class TaskRepositoryFake:
    def __init__(self) -> None:
        self.requested: list[str] = []

    def get(self, task_id: str) -> Task:
        self.requested.append(task_id)
        if task_id != "TF-1":
            raise FileNotFoundError(task_id)
        return Task(task_id=task_id)

    def save(self, task: Task) -> Task:
        return task


class AgentRepositoryFake:
    def __init__(self, *agents: Agent) -> None:
        self.records = {(agent.parent_task_id, agent.agent_id): agent for agent in agents}

    def get(self, task_id: str, agent_id: str) -> Agent:
        return self.records[(task_id, agent_id)]

    def save(self, agent: Agent) -> Agent:
        self.records[(agent.parent_task_id, agent.agent_id)] = agent
        return agent

    def exists(self, task_id: str, agent_id: str) -> bool:
        return (task_id, agent_id) in self.records

    def list(self, *, task_id: str | None = None) -> tuple[Agent, ...]:
        return tuple(
            agent
            for agent in self.records.values()
            if task_id is None or agent.parent_task_id == task_id
        )


class FixedClock:
    def now(self) -> str:
        return "2026-07-19T12:00:00Z"


class AgentManagementApplicationTests(unittest.TestCase):
    def test_register_validates_parent_and_creates_canonical_timestamps(self) -> None:
        service, tasks, agents = _service()

        view = service.register(
            RegisterAgentCommand(
                task_id="TF-1",
                agent_id="worker-1",
                role="worker",
                owned_paths=("src",),
            )
        )

        self.assertEqual(tasks.requested, ["TF-1"])
        self.assertEqual(view.agent.started_at, "2026-07-19T12:00:00Z")
        self.assertEqual(view.effective_status, "running")
        self.assertEqual(agents.get("TF-1", "worker-1").owned_paths, ("src",))

    def test_register_rejects_duplicate_before_replacing_record(self) -> None:
        existing = Agent(agent_id="worker-1", parent_task_id="TF-1", role="worker")
        service, _, agents = _service(existing)

        with self.assertRaisesRegex(AgentManagementError, "already exists"):
            service.register(
                RegisterAgentCommand(task_id="TF-1", agent_id="worker-1", role="worker")
            )

        self.assertIs(agents.get("TF-1", "worker-1"), existing)

    def test_final_update_sets_finished_time_and_clears_pid(self) -> None:
        existing = Agent(
            agent_id="worker-1",
            parent_task_id="TF-1",
            role="worker",
            status="running",
            pid=4242,
            started_at="2026-07-19T11:00:00Z",
            updated_at="2026-07-19T11:00:00Z",
        )
        service, _, _ = _service(existing)

        view = service.update(
            UpdateAgentCommand(
                task_id="TF-1",
                agent_id="worker-1",
                status="failed",
                error="exit 7",
            )
        )

        self.assertEqual(view.agent.finished_at, "2026-07-19T12:00:00Z")
        self.assertIsNone(view.agent.pid)
        self.assertEqual(view.agent.error, "exit 7")

    def test_list_derives_stale_without_mutating_persisted_status(self) -> None:
        existing = Agent(
            agent_id="worker-1",
            parent_task_id="TF-1",
            role="worker",
            status="running",
            updated_at="2000-01-01T00:00:00Z",
            last_heartbeat_at="2000-01-01T00:00:00Z",
        )
        service, _, agents = _service(existing)

        views = service.list(task_id="TF-1", stale_after_seconds=60)

        self.assertEqual(views[0].raw_status, "running")
        self.assertEqual(views[0].effective_status, "stale")
        self.assertEqual(agents.get("TF-1", "worker-1").status, "running")


def _service(
    *agents: Agent,
) -> tuple[AgentManagementService, TaskRepositoryFake, AgentRepositoryFake]:
    tasks = TaskRepositoryFake()
    repository = AgentRepositoryFake(*agents)
    return (
        AgentManagementService(tasks=tasks, agents=repository, clock=FixedClock()),
        tasks,
        repository,
    )


if __name__ == "__main__":
    unittest.main()
