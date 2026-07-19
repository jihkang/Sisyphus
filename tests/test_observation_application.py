from __future__ import annotations

import unittest

from sisyphus.application.observation import project_task_observation


class ObservationApplicationTests(unittest.TestCase):
    def test_projection_is_deterministic_and_uses_precomputed_boundary_inputs(self) -> None:
        task = {
            "id": "TF-1",
            "type": "feature",
            "slug": "observe",
            "workflow_phase": "execution",
            "status": "open",
            "stage": "spec",
            "plan_status": "approved",
            "spec_status": "frozen",
            "verify_status": "not_run",
            "audit_attempts": 0,
            "max_audit_attempts": 3,
            "last_verify_results": [],
            "gates": [],
            "subtasks": [{"status": "queued"}, {"status": "completed"}],
            "promotion": {"required": True, "status": "promotion_pending"},
        }
        kwargs = {
            "required_docs": {"brief": "present", "plan": "present"},
            "evidence_summary": {"status": "not_required", "blocking_gaps": 0},
            "allowed_next_actions": ("sisyphus.get_task",),
            "forbidden_next_actions": (
                {
                    "action": "sisyphus.close_task",
                    "risk": "review_gated",
                    "requires_human": True,
                    "reason": "verify first",
                    "gates": [],
                },
            ),
        }

        first = project_task_observation(task, **kwargs)
        second = project_task_observation(task, **kwargs)

        self.assertEqual(first, second)
        self.assertTrue(str(first["observation_hash"]).startswith("sha256:"))
        self.assertEqual(first["required_docs"], kwargs["required_docs"])
        self.assertEqual(first["evidence_summary"], kwargs["evidence_summary"])
        self.assertEqual(first["allowed_next_actions"], ["sisyphus.get_task"])
        self.assertEqual(first["subtasks"]["queued"], 1)
        self.assertEqual(first["subtasks"]["completed"], 1)


if __name__ == "__main__":
    unittest.main()
