from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from ..shared.coerce import optional_str


EVOLUTION_RUNS_DIR_NAME = "runs"
EVOLUTION_RUN_ARTIFACT_NAMES = (
    "run.json",
    "dataset.json",
    "harness_plan.json",
    "constraints.json",
    "fitness.json",
    "report.md",
    "failure.json",
)


@dataclass(frozen=True, slots=True)
class EvolutionRunArtifacts:
    repo_root: str
    run_id: str
    artifact_dir: str
    run: Mapping[str, object]
    dataset: Mapping[str, object] | None
    harness_plan: Mapping[str, object] | None
    constraints: Mapping[str, object] | None
    fitness: Mapping[str, object] | None
    report_markdown: str | None
    failure: Mapping[str, object] | None
    available_artifact_names: tuple[str, ...] = ()

    @property
    def run_record(self) -> Mapping[str, object]:
        run = self.run.get("run")
        if isinstance(run, Mapping):
            return run
        return self.run

    @property
    def final_stage(self) -> str:
        if self.failure is not None:
            return "failed"
        if self.report_markdown is not None:
            return "report_built"
        if self.fitness is not None:
            return "fitness_evaluated"
        if self.constraints is not None:
            return "constraints_evaluated"
        if self.harness_plan is not None:
            return "harness_planned"
        if self.dataset is not None:
            return "dataset_built"
        return "planned"

    @property
    def run_status(self) -> str:
        value = optional_str(self.run_record.get("status"))
        return value or "planned"

    @property
    def selection_mode(self) -> str:
        value = optional_str(self.run_record.get("selection_mode"))
        return value or "unknown"

    @property
    def target_ids(self) -> tuple[str, ...]:
        return _string_tuple(self.run_record.get("target_ids"))

    @property
    def dataset_task_count(self) -> int | None:
        if self.dataset is None:
            return None
        value = self.dataset.get("task_count")
        return int(value) if isinstance(value, int) else None

    @property
    def dataset_event_count(self) -> int | None:
        if self.dataset is None:
            return None
        value = self.dataset.get("event_count")
        return int(value) if isinstance(value, int) else None

    @property
    def report_status(self) -> str:
        if self.constraints is not None and self._constraint_accepted() is False:
            return "rejected"
        if self.fitness is not None and optional_str(self.fitness.get("status")) == "scored":
            return "ready_for_review"
        return "planned"

    @property
    def recommendation(self) -> str:
        if self.report_status == "rejected":
            return "reject_candidate"
        if self.report_status == "ready_for_review":
            return "review_candidate"
        return "await_execution"

    @property
    def constraint_status(self) -> str | None:
        if self.constraints is None:
            return None
        return optional_str(self.constraints.get("status")) or None

    @property
    def fitness_status(self) -> str | None:
        if self.fitness is None:
            return None
        return optional_str(self.fitness.get("status")) or None

    @property
    def score_delta(self) -> float | None:
        if self.fitness is None:
            return None
        value = self.fitness.get("score_delta")
        if isinstance(value, (int, float)):
            return float(value)
        return None

    @property
    def available_artifacts(self) -> tuple[str, ...]:
        return self.available_artifact_names

    @property
    def report_path(self) -> str:
        return "report.md"

    def _constraint_accepted(self) -> bool | None:
        if self.constraints is None:
            return None
        accepted = self.constraints.get("accepted")
        if isinstance(accepted, bool):
            return accepted
        return None

@dataclass(frozen=True, slots=True)
class EvolutionRunComparison:
    left_run_id: str
    right_run_id: str
    lines: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class EvolutionExecutionSurfaceResult:
    ok: bool
    run_id: str | None
    artifact_dir: str | None
    resource_uri: str | None
    final_stage: str | None
    content: str
    error: str | None = None
    error_type: str | None = None
    failure_stage: str | None = None


def summarize_evolution_run(artifacts: EvolutionRunArtifacts) -> tuple[str, ...]:
    lines = [
        f"Run ID: {artifacts.run_id}",
        f"Artifact Dir: {artifacts.artifact_dir}",
        f"Final Stage: {artifacts.final_stage}",
        f"Run Status: {artifacts.run_status}",
        f"Report Status: {artifacts.report_status}",
        f"Recommendation: {artifacts.recommendation}",
        f"Selection Mode: {artifacts.selection_mode}",
        f"Target IDs: {', '.join(artifacts.target_ids) or 'none'}",
    ]
    if artifacts.dataset_task_count is not None:
        lines.append(f"Dataset Tasks: {artifacts.dataset_task_count}")
    if artifacts.dataset_event_count is not None:
        lines.append(f"Dataset Events: {artifacts.dataset_event_count}")
    if artifacts.constraint_status is not None:
        lines.append(f"Constraints: {artifacts.constraint_status}")
    if artifacts.fitness_status is not None:
        lines.append(f"Fitness: {artifacts.fitness_status}")
    if artifacts.score_delta is not None:
        lines.append(f"Fitness Score Delta: {artifacts.score_delta:+.2f}")
    if artifacts.failure is not None:
        lines.append(f"Failure Stage: {optional_str(artifacts.failure.get('stage')) or 'unknown'}")
        lines.append(f"Failure Type: {optional_str(artifacts.failure.get('error_type')) or 'unknown'}")
        lines.append(f"Failure Message: {optional_str(artifacts.failure.get('message')) or 'unknown'}")
    lines.append(f"Available Artifacts: {', '.join(artifacts.available_artifacts) or 'none'}")
    return tuple(lines)


def render_evolution_run_overview(artifacts: EvolutionRunArtifacts) -> str:
    lines = [
        f"evolution run {artifacts.run_id}",
        f"artifact_dir: {artifacts.artifact_dir}",
        f"final_stage: {artifacts.final_stage}",
        f"run_status: {artifacts.run_status}",
        f"report_status: {artifacts.report_status}",
        f"recommendation: {artifacts.recommendation}",
        f"selection_mode: {artifacts.selection_mode}",
        f"target_ids: {', '.join(artifacts.target_ids) or 'none'}",
    ]
    if artifacts.dataset_task_count is not None:
        lines.append(f"dataset_task_count: {artifacts.dataset_task_count}")
    if artifacts.dataset_event_count is not None:
        lines.append(f"dataset_event_count: {artifacts.dataset_event_count}")
    if artifacts.constraint_status is not None:
        lines.append(f"constraint_status: {artifacts.constraint_status}")
    if artifacts.fitness_status is not None:
        lines.append(f"fitness_status: {artifacts.fitness_status}")
    if artifacts.score_delta is not None:
        lines.append(f"fitness_score_delta: {artifacts.score_delta:+.2f}")
    lines.append("artifacts:")
    for name in artifacts.available_artifacts:
        lines.append(f"- {name}")
    if artifacts.failure is not None:
        lines.append("failure:")
        lines.append(f"- stage: {optional_str(artifacts.failure.get('stage')) or 'unknown'}")
        lines.append(f"- error_type: {optional_str(artifacts.failure.get('error_type')) or 'unknown'}")
        lines.append(f"- message: {optional_str(artifacts.failure.get('message')) or 'unknown'}")
    return "\n".join(lines) + "\n"


def render_evolution_run_status(artifacts: EvolutionRunArtifacts) -> str:
    return "\n".join(summarize_evolution_run(artifacts)) + "\n"


def render_evolution_run_report(artifacts: EvolutionRunArtifacts) -> str:
    if artifacts.report_markdown is not None:
        report = artifacts.report_markdown
        return report if report.endswith("\n") else f"{report}\n"

    lines = [
        "# Evolution Report",
        "",
        f"- Run ID: `{artifacts.run_id}`",
        f"- Final Stage: `{artifacts.final_stage}`",
        f"- Status: `{artifacts.report_status}`",
        f"- Recommendation: `{artifacts.recommendation}`",
        "",
        "## Summary",
    ]
    lines.extend(f"- {line}" for line in summarize_evolution_run(artifacts))
    return "\n".join(lines) + "\n"


def compare_evolution_runs(left: EvolutionRunArtifacts, right: EvolutionRunArtifacts) -> EvolutionRunComparison:
    lines = [
        f"Left Run: {left.run_id}",
        f"Right Run: {right.run_id}",
        f"Final Stage: {left.final_stage} -> {right.final_stage}",
        f"Report Status: {left.report_status} -> {right.report_status}",
        f"Recommendation: {left.recommendation} -> {right.recommendation}",
        f"Selection Mode: {left.selection_mode} -> {right.selection_mode}",
        f"Target IDs: {', '.join(left.target_ids) or 'none'} -> {', '.join(right.target_ids) or 'none'}",
    ]
    lines.append(
        f"Dataset Tasks: {left.dataset_task_count if left.dataset_task_count is not None else 'n/a'}"
        f" -> {right.dataset_task_count if right.dataset_task_count is not None else 'n/a'}"
    )
    lines.append(
        f"Dataset Events: {left.dataset_event_count if left.dataset_event_count is not None else 'n/a'}"
        f" -> {right.dataset_event_count if right.dataset_event_count is not None else 'n/a'}"
    )
    lines.append(
        f"Constraints: {left.constraint_status or 'n/a'} -> {right.constraint_status or 'n/a'}"
    )
    lines.append(f"Fitness: {left.fitness_status or 'n/a'} -> {right.fitness_status or 'n/a'}")
    lines.append(
        f"Fitness Score Delta: "
        f"{_format_float(left.score_delta)} -> {_format_float(right.score_delta)}"
    )
    lines.append(
        f"Available Artifacts: {len(left.available_artifacts)} -> {len(right.available_artifacts)}"
    )
    if left.report_markdown is not None and right.report_markdown is not None:
        lines.append(
            f"Report Length: {len(left.report_markdown.splitlines())} -> {len(right.report_markdown.splitlines())}"
        )
    return EvolutionRunComparison(
        left_run_id=left.run_id,
        right_run_id=right.run_id,
        lines=tuple(lines),
    )


def render_evolution_run_compare(comparison: EvolutionRunComparison) -> str:
    return "\n".join(
        [
            f"evolution compare {comparison.left_run_id} {comparison.right_run_id}",
            *comparison.lines,
        ]
    ) + "\n"


def evolution_run_uri(run_id: str, view: str) -> str:
    return f"evolution://{run_id}/{view}"


def _string_tuple(value: object) -> tuple[str, ...]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        return ()
    return tuple(str(item) for item in value if str(item).strip())


def _format_float(value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"{value:+.2f}"
