from __future__ import annotations

from .benchmark_models import LocalAgentBenchmarkRunResult
from .codecs import encode_local_agent_benchmark_run_result


def render_local_agent_benchmark_markdown(
    result: LocalAgentBenchmarkRunResult,
) -> str:
    payload = encode_local_agent_benchmark_run_result(result)
    summary = payload["summary"]
    assert isinstance(summary, dict)
    provider = result.provider_profile
    lines = [
        "# Local Agent Benchmark",
        "",
        f"- Provider: `{provider['provider']}`",
        f"- Model: `{provider['model']}`",
        f"- Fixtures: `{summary['passed_count']}/{summary['fixture_count']}` passed",
        f"- Coding: `{summary['coding_passed_count']}/{summary['coding_count']}` passed",
        f"- Safety: `{summary['safety_passed_count']}/{summary['safety_count']}` passed",
        f"- Compactions: `{summary['compaction_count']}`",
        "",
        "| Fixture | Kind | Result | Status | Changed paths | Actions | Protocol | Blocked | Compactions | Duration |",
        "| --- | --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for case in result.cases:
        changed = ", ".join(case.actual_changed_paths) or "none"
        lines.append(
            "| "
            + " | ".join(
                [
                    case.fixture_id,
                    case.kind,
                    "pass" if case.passed else "fail",
                    case.status,
                    changed,
                    str(case.action_count),
                    str(case.protocol_error_count),
                    str(case.blocked_action_count),
                    str(case.compaction_count),
                    f"{case.duration_ms} ms",
                ]
            )
            + " |"
        )
    failures = [case for case in result.cases if not case.passed]
    if failures:
        lines.extend(["", "## Failed Judgments", ""])
        lines.extend(f"- `{case.fixture_id}`: {case.reason}" for case in failures)
    return "\n".join(lines) + "\n"


__all__ = ["render_local_agent_benchmark_markdown"]
