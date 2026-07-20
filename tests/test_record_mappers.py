from __future__ import annotations

from dataclasses import replace
from enum import Enum
import sys
from pathlib import Path
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from sisyphus.domain.agent.models import Agent
from sisyphus.domain.task.models import Task
from sisyphus.infra.persistence.agent_mapper import AGENT_RECORD_MAPPER
from sisyphus.infra.persistence.record_mapper import RecordEnvelope
from sisyphus.infra.persistence.task_mapper import TASK_RECORD_MAPPER
from sisyphus.shared.serialization import to_json_value


class RecordMapperTests(unittest.TestCase):
    def test_task_unknown_fields_round_trip_without_loss(self) -> None:
        raw = {
            "id": "TF-test",
            "type": "feature",
            "slug": "test",
            "status": "open",
            "stage": "spec",
            "workflow_phase": "execution",
            "plan_status": "approved",
            "spec_status": "frozen",
            "verify_status": "passed",
            "future_schema": {"nested": [1, {"enabled": True}]},
            "subtasks": [{"id": "subtask-001"}],
        }

        envelope = TASK_RECORD_MAPPER.decode(raw)
        encoded = TASK_RECORD_MAPPER.encode(envelope)

        self.assertEqual(encoded, raw)
        self.assertEqual(list(encoded), list(raw))
        self.assertEqual(envelope.model.task_id, "TF-test")
        self.assertEqual(envelope.extensions["future_schema"], raw["future_schema"])

    def test_mapper_deep_copies_unknown_fields(self) -> None:
        raw = {"id": "TF-test", "future_schema": {"items": ["original"]}}

        envelope = TASK_RECORD_MAPPER.decode(raw)
        raw["future_schema"]["items"].append("mutated")
        encoded = TASK_RECORD_MAPPER.encode(envelope)

        self.assertEqual(encoded["future_schema"], {"items": ["original"]})

    def test_missing_known_fields_remain_missing_on_round_trip(self) -> None:
        raw = {"id": "TF-test", "custom": 1}

        encoded = TASK_RECORD_MAPPER.encode(TASK_RECORD_MAPPER.decode(raw))

        self.assertEqual(encoded, raw)

    def test_domain_update_preserves_extensions(self) -> None:
        envelope = TASK_RECORD_MAPPER.decode(
            {
                "id": "TF-test",
                "status": "open",
                "verify_status": "not_run",
                "future_schema": {"owner": "external"},
            }
        )
        updated = RecordEnvelope(
            model=replace(envelope.model, status="blocked", verify_status="failed"),
            extensions=envelope.extensions,
            present_fields=envelope.present_fields,
        )

        encoded = TASK_RECORD_MAPPER.encode(updated)

        self.assertEqual(encoded["status"], "blocked")
        self.assertEqual(encoded["verify_status"], "failed")
        self.assertEqual(encoded["future_schema"], {"owner": "external"})

    def test_new_task_includes_all_configured_defaults(self) -> None:
        encoded = TASK_RECORD_MAPPER.encode(TASK_RECORD_MAPPER.envelope_for(Task(task_id="TF-new")))

        self.assertEqual(encoded["id"], "TF-new")
        self.assertEqual(encoded["status"], "open")
        self.assertEqual(encoded["plan_status"], "pending_review")
        self.assertEqual(encoded["verify_status"], "not_run")

    def test_agent_tuple_fields_round_trip_as_json_arrays(self) -> None:
        raw = {
            "agent_id": "agent-1",
            "parent_task_id": "TF-test",
            "role": "worker",
            "status": "running",
            "owned_paths": ["src/sisyphus"],
            "command": ["python", "-m", "worker"],
            "provider_extension": {"retry": 2},
        }

        envelope = AGENT_RECORD_MAPPER.decode(raw)
        encoded = AGENT_RECORD_MAPPER.encode(envelope)

        self.assertEqual(envelope.model.owned_paths, ("src/sisyphus",))
        self.assertEqual(envelope.model.command, ("python", "-m", "worker"))
        self.assertEqual(encoded, raw)

    def test_agent_mapper_rejects_malformed_array_fields(self) -> None:
        raw = {
            "agent_id": "agent-1",
            "parent_task_id": "TF-test",
            "role": "worker",
            "owned_paths": "src/sisyphus",
        }

        with self.assertRaisesRegex(ValueError, "JSON array of strings"):
            AGENT_RECORD_MAPPER.decode(raw)

    def test_agent_mapper_accepts_legacy_in_memory_tuples(self) -> None:
        raw = {
            "agent_id": "agent-1",
            "parent_task_id": "TF-test",
            "role": "worker",
            "owned_paths": ("src",),
            "command": (),
        }

        encoded = AGENT_RECORD_MAPPER.encode(AGENT_RECORD_MAPPER.decode(raw))

        self.assertEqual(encoded["owned_paths"], ["src"])
        self.assertEqual(encoded["command"], [])

    def test_entities_do_not_own_serialization_methods(self) -> None:
        self.assertFalse(hasattr(Task, "to_dict"))
        self.assertFalse(hasattr(Agent, "to_dict"))


class SerializationUtilityTests(unittest.TestCase):
    def test_serializes_nested_dataclasses_tuples_and_enums(self) -> None:
        class Status(str, Enum):
            OPEN = "open"

        value = {
            "task": Task(task_id="TF-test"),
            "agent": Agent("agent-1", "TF-test", "worker", owned_paths=("src",)),
            "status": Status.OPEN,
        }

        encoded = to_json_value(value)

        self.assertEqual(encoded["task"]["task_id"], "TF-test")
        self.assertEqual(encoded["agent"]["owned_paths"], ["src"])
        self.assertEqual(encoded["status"], "open")
        self.assertIs(type(encoded["status"]), str)

    def test_rejects_non_string_mapping_keys(self) -> None:
        with self.assertRaisesRegex(TypeError, "keys must be strings"):
            to_json_value({1: "invalid"})


if __name__ == "__main__":
    unittest.main()
