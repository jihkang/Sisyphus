from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path

from ..config import SisyphusConfig
from ..episode_trace import read_episode_steps
from ..observation import build_task_observation
from ..reward import RewardBreakdown, reward_breakdown_metrics, score_task_outcome
from ..state import load_task_record
from ..test_first import TEST_FIRST_LOOP_PHASES, TestFirstEvaluation, evaluate_test_first_loop


EVAL_LOOP_SCHEMA_VERSION = "sisyphus.eval_loop.v1"
EVAL_LOOP_SHAPE = (
    "observation_t",
    "action_t",
    "transition_result_t",
    "observation_t_plus_1",
    "reward_t",
)
@dataclass(frozen=True, slots=True)
class EvalLoopResult:
    task_id: str
    mode: str
    observation_ref: str
    initial_observation_hash: str
    final_observation_hash: str
    episode_id: str | None
    step_count: int
    action_count: int
    terminal_status: str
    reward: RewardBreakdown
    metrics: dict[str, float]
    actions: tuple[dict[str, object], ...]
    test_first: TestFirstEvaluation

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": EVAL_LOOP_SCHEMA_VERSION,
            "task_id": self.task_id,
            "mode": self.mode,
            "loop": {
                "shape": list(EVAL_LOOP_SHAPE),
                "test_first": self.test_first.to_dict(),
            },
            "observation": {
                "ref": self.observation_ref,
                "initial_hash": self.initial_observation_hash,
                "final_hash": self.final_observation_hash,
            },
            "episode": {
                "episode_id": self.episode_id,
                "step_count": self.step_count,
                "action_count": self.action_count,
            },
            "actions": list(self.actions),
            "outcome": {
                "terminal_status": self.terminal_status,
                "facts": asdict(self.reward.facts),
            },
            "reward": {
                "total": self.reward.total,
                "components": self.metrics,
                "penalties": dict(self.reward.penalties),
            },
            "metrics": self.metrics,
        }


def run_task_eval_loop(
    repo_root: Path,
    config: SisyphusConfig,
    task_id: str,
    *,
    episode_id: str | None = None,
    max_action_count: int = 50,
) -> EvalLoopResult:
    task, task_file = load_task_record(repo_root=repo_root, task_dir_name=config.task_dir, task_id=task_id)
    return build_task_eval_loop_result(
        task,
        task_file.parent,
        episode_id=episode_id,
        max_action_count=max_action_count,
    )


def build_task_eval_loop_result(
    task: dict,
    task_dir: Path,
    *,
    episode_id: str | None = None,
    max_action_count: int = 50,
) -> EvalLoopResult:
    observation = build_task_observation(task, task_dir)
    steps = read_episode_steps(task_dir, episode_id=episode_id)
    reward = score_task_outcome(
        task,
        task_dir,
        episode_steps=steps,
        max_action_count=max_action_count,
    )
    metrics = reward_breakdown_metrics(reward)
    action_summaries = tuple(_action_summary(step) for step in steps if _has_action(step))
    test_first = evaluate_test_first_loop(steps)
    current_hash = str(observation.get("observation_hash") or "")
    initial_hash = _initial_observation_hash(steps) or current_hash
    return EvalLoopResult(
        task_id=str(task.get("id") or ""),
        mode="recorded_offline",
        observation_ref=f"task://{task.get('id')}/observation",
        initial_observation_hash=initial_hash,
        final_observation_hash=current_hash,
        episode_id=episode_id,
        step_count=len(steps),
        action_count=len(action_summaries),
        terminal_status=_terminal_status(reward),
        reward=reward,
        metrics=metrics,
        actions=action_summaries,
        test_first=test_first,
    )


def _terminal_status(reward: RewardBreakdown) -> str:
    facts = reward.facts
    if facts.false_close:
        return "false_closed"
    if facts.status == "closed":
        if facts.verify_status == "passed" and facts.conformance_status == "green":
            return "closed_verified"
        return "closed_with_gates"
    if facts.verify_status == "failed":
        return "verification_failed"
    if facts.conformance_status in {"yellow", "red"}:
        return "conformance_drift"
    if facts.blocking_gate_count:
        return "blocked"
    if facts.verify_status == "passed":
        return "verified_not_closed"
    return "open"


def _has_action(step: dict[str, object]) -> bool:
    action = step.get("action")
    return isinstance(action, dict) and bool(action.get("name"))


def _action_summary(step: dict[str, object]) -> dict[str, object]:
    action = step.get("action")
    result = step.get("result")
    action_dict = action if isinstance(action, dict) else {}
    result_dict = result if isinstance(result, dict) else {}
    return {
        "step": step.get("step"),
        "name": action_dict.get("name"),
        "result_ok": result_dict.get("ok"),
        "observation_hash": step.get("observation_hash"),
    }


def _initial_observation_hash(steps: list[dict[str, object]]) -> str | None:
    for step in steps:
        value = step.get("observation_hash")
        if isinstance(value, str) and value:
            return value
    return None


__all__ = [
    "EVAL_LOOP_SCHEMA_VERSION",
    "EVAL_LOOP_SHAPE",
    "TEST_FIRST_LOOP_PHASES",
    "EvalLoopResult",
    "build_task_eval_loop_result",
    "run_task_eval_loop",
]
