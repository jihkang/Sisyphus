from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from sisyphus.bus import NoopEventPublisher, build_event_publisher
from sisyphus.bus_jsonl import JsonlEventPublisher, read_jsonl_events, resolve_event_bus_path
from sisyphus.config import load_config
from sisyphus.events import EventEnvelope, new_event_envelope, normalize_event_envelope
from sisyphus.infra.events import JsonlEventPublisher as CanonicalJsonlEventPublisher


class EventBusTests(unittest.TestCase):
    def test_public_jsonl_publisher_preserves_canonical_identity(self) -> None:
        self.assertIs(JsonlEventPublisher, CanonicalJsonlEventPublisher)

    def test_load_config_defaults_event_bus_to_noop(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            repo_root = Path(tempdir)

            config = load_config(repo_root)

            self.assertEqual(config.event_bus.provider, "noop")
            self.assertEqual(config.event_bus.jsonl_path, ".planning/events.jsonl")

    def test_load_config_parses_event_bus_section(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            repo_root = Path(tempdir)
            (repo_root / ".taskflow.toml").write_text(
                "\n".join(
                    [
                        '[event_bus]',
                        'provider = "jsonl"',
                        'jsonl_path = ".planning/custom-events.jsonl"',
                        "",
                    ]
                ),
                encoding="utf-8",
            )

            config = load_config(repo_root)

            self.assertEqual(config.event_bus.provider, "jsonl")
            self.assertEqual(config.event_bus.jsonl_path, ".planning/custom-events.jsonl")

    def test_load_config_prefers_sisyphus_toml_over_legacy_taskflow_toml(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            repo_root = Path(tempdir)
            (repo_root / ".taskflow.toml").write_text('base_branch = "legacy"\n', encoding="utf-8")
            (repo_root / ".sisyphus.toml").write_text('base_branch = "canonical"\n', encoding="utf-8")

            config = load_config(repo_root)

            self.assertEqual(config.base_branch, "canonical")

    def test_load_config_uses_legacy_taskflow_toml_as_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            repo_root = Path(tempdir)
            (repo_root / ".taskflow.toml").write_text('base_branch = "legacy"\n', encoding="utf-8")

            config = load_config(repo_root)

            self.assertEqual(config.base_branch, "legacy")

    def test_event_envelope_round_trips_from_mapping(self) -> None:
        envelope = normalize_event_envelope(
            {
                "event_type": "task.created",
                "event_id": "evt_123",
                "timestamp": "2026-04-13T00:00:00Z",
                "schema_version": "taskflow.event.v1",
                "source": {"module": "tests"},
                "data": {"task_id": "TF-1"},
            }
        )

        self.assertIsInstance(envelope, EventEnvelope)
        self.assertEqual(envelope.event_type, "task.created")
        self.assertEqual(envelope.event_id, "evt_123")
        self.assertEqual(envelope.source["module"], "tests")
        self.assertEqual(envelope.data["task_id"], "TF-1")

    def test_jsonl_publisher_appends_envelope(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            repo_root = Path(tempdir)
            (repo_root / ".taskflow.toml").write_text(
                "\n".join(
                    [
                        '[event_bus]',
                        'provider = "jsonl"',
                        'jsonl_path = ".planning/events/domain-events.jsonl"',
                        "",
                    ]
                ),
                encoding="utf-8",
            )
            config = load_config(repo_root)
            publisher = build_event_publisher(repo_root, config)

            self.assertIsInstance(publisher, JsonlEventPublisher)
            self.assertEqual(resolve_event_bus_path(repo_root, config), repo_root / ".planning/events/domain-events.jsonl")

            event = new_event_envelope(
                "task.updated",
                source={"module": "tests"},
                data={"task_id": "TF-1", "status": "open"},
                event_id="evt_456",
                timestamp="2026-04-13T00:00:00Z",
            )
            publisher.publish(event)

            payload = (repo_root / ".planning/events/domain-events.jsonl").read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(payload), 1)
            decoded = json.loads(payload[0])
            self.assertEqual(decoded["event_type"], "task.updated")
            self.assertEqual(decoded["event_id"], "evt_456")
            self.assertEqual(decoded["source"]["module"], "tests")
            self.assertEqual(decoded["data"]["status"], "open")

    def test_jsonl_publisher_serializes_concurrent_durable_appends(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            path = Path(tempdir) / "events.jsonl"
            publisher = JsonlEventPublisher(path)

            def publish(index: int) -> None:
                publisher.publish(
                    new_event_envelope(
                        "task.updated",
                        event_id=f"evt_{index}",
                        data={"index": index},
                    )
                )

            with (
                mock.patch("sisyphus.infra.events.publishers.os.fsync") as fsync,
                mock.patch(
                    "sisyphus.infra.events.publishers.fsync_directory"
                ) as fsync_directory,
            ):
                with ThreadPoolExecutor(max_workers=8) as executor:
                    list(executor.map(publish, range(40)))

            events = read_jsonl_events(path, limit=100)
            self.assertEqual(len(events), 40)
            self.assertEqual({event["event_id"] for event in events}, {f"evt_{i}" for i in range(40)})
            self.assertEqual(fsync.call_count, 40)
            fsync_directory.assert_called_once_with(path.parent)

    @unittest.skipUnless(getattr(os, "O_NOFOLLOW", 0), "O_NOFOLLOW is unavailable")
    def test_jsonl_publisher_rejects_symbolic_link_target(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            outside = root / "outside.jsonl"
            outside.write_text("original\n", encoding="utf-8")
            path = root / "events.jsonl"
            path.symlink_to(outside)

            with self.assertRaises(OSError):
                JsonlEventPublisher(path).publish(
                    new_event_envelope("task.updated", event_id="evt_symlink")
                )
            with self.assertRaises(OSError):
                read_jsonl_events(path)

            self.assertEqual(outside.read_text(encoding="utf-8"), "original\n")

    def test_noop_publisher_accepts_events(self) -> None:
        publisher = NoopEventPublisher()
        publisher.publish(new_event_envelope("task.blocked", data={"task_id": "TF-1"}))

    def test_read_jsonl_events_returns_recent_entries(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            path = Path(tempdir) / "events.jsonl"
            path.write_text(
                "\n".join(
                    [
                        json.dumps({"event_id": "evt_1", "event_type": "task.created"}),
                        json.dumps({"event_id": "evt_2", "event_type": "task.updated"}),
                        json.dumps({"event_id": "evt_3", "event_type": "verify.completed"}),
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            files_before = {entry.name for entry in path.parent.iterdir()}
            events = read_jsonl_events(path, limit=2)

            self.assertEqual([event["event_id"] for event in events], ["evt_2", "evt_3"])
            self.assertEqual({entry.name for entry in path.parent.iterdir()}, files_before)


if __name__ == "__main__":
    unittest.main()
