from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import json

from .conformance import build_execution_contract
from .config import SisyphusConfig
from .context_pack import build_task_execution_context_pack
from .discipline import build_sisyphus_worker_discipline
from .state import load_task_record
from .utils import project_fields


@dataclass(slots=True)
class CodexPrompt:
    task_id: str
    workdir: Path
    prompt: str
    context_pack: dict[str, object] | None = None
    context_pack_path: Path | None = None


def build_codex_prompt(
    repo_root: Path,
    config: SisyphusConfig,
    task_id: str,
    *,
    extra_instruction: str | None = None,
) -> CodexPrompt:
    task, task_file = load_task_record(repo_root=repo_root, task_dir_name=config.task_dir, task_id=task_id)
    task_dir = task_file.parent
    workdir = _resolve_workdir(repo_root=repo_root, task=task)
    docs = _load_docs(task=task, task_dir=task_dir)
    task_snapshot = _build_task_snapshot(task)
    context_pack, context_pack_path = build_task_execution_context_pack(
        repo_root,
        config,
        task=task,
        docs=docs,
    )

    sections = [
        "You are the local Codex worker for this task.",
        "Read the task metadata and docs below, inspect the repository state in the assigned worktree, then carry out the task.",
        "Keep changes aligned with the documented acceptance criteria and test strategy.",
        "If the task docs and code disagree, prefer the task docs and update code accordingly.",
        "Run relevant validation before finishing when feasible.",
        "Task docs live under the repository-relative paths shown in each section heading.",
        "Start your final response with exactly one status line: `STATUS: completed`, `STATUS: blocked`, or `STATUS: failed`.",
    ]
    if extra_instruction:
        sections.append(f"Additional operator instruction: {extra_instruction}")

    body = [
        "\n".join(sections),
        *_render_discipline_sections(),
        "## Execution Contract",
        build_execution_contract(task),
        "## Task Metadata",
        json.dumps(task_snapshot, indent=2),
        *_render_context_pack_sections(context_pack, context_pack_path),
    ]

    for name, content in docs:
        body.extend(
            [
                f"## {name}",
                content.strip(),
            ]
        )

    return CodexPrompt(
        task_id=task["id"],
        workdir=workdir,
        prompt="\n\n".join(body).strip() + "\n",
        context_pack=context_pack,
        context_pack_path=context_pack_path,
    )


def _render_discipline_sections() -> list[str]:
    rendered: list[str] = []
    for title, bullets in build_sisyphus_worker_discipline():
        rendered.append(f"## {title}")
        rendered.extend(f"- {bullet}" for bullet in bullets)
    return rendered


def _render_context_pack_sections(context_pack: dict[str, object], context_pack_path: Path) -> list[str]:
    lines = [
        "## ContextPack",
        "",
        "Use this as supporting evidence only. The frozen task docs and execution contract remain authoritative.",
        "",
        f"- Pack ID: `{context_pack.get('pack_id')}`",
        f"- Fingerprint: `{context_pack.get('fingerprint')}`",
        f"- Path: `{context_pack_path}`",
        f"- Purpose: `{context_pack.get('purpose') or 'n/a'}`",
        f"- Source Task ID: `{context_pack.get('source_task_id') or 'n/a'}`",
        f"- Query: `{context_pack.get('query') or ''}`",
        f"- Results: `{context_pack.get('result_count')}`",
    ]
    excluded_task_ids = context_pack.get("excluded_task_ids")
    if isinstance(excluded_task_ids, list) and excluded_task_ids:
        lines.append(f"- Excluded Task IDs: `{', '.join(str(task_id) for task_id in excluded_task_ids)}`")

    items = context_pack.get("items")
    if not isinstance(items, list) or not items:
        lines.extend(["", "No ContextPack results selected."])
        return lines

    lines.append("")
    for item in items:
        if not isinstance(item, dict):
            continue
        matched_terms = item.get("matched_terms")
        if isinstance(matched_terms, list):
            matched_terms_text = ", ".join(str(term) for term in matched_terms)
        else:
            matched_terms_text = ""
        lines.extend(
            [
                f"### Context Item {item.get('rank')}",
                "",
                f"- Source Ref: `{item.get('source_ref')}`",
                f"- Source Type: `{item.get('source_type')}`",
                f"- Task ID: `{item.get('task_id') or 'n/a'}`",
                f"- Title: `{item.get('title') or ''}`",
                f"- Score: `{item.get('score')}`",
                f"- Freshness: `{item.get('freshness_status') or 'n/a'}`",
                f"- Document Fingerprint: `{item.get('document_fingerprint')}`",
                f"- Matched Terms: `{matched_terms_text}`",
                "",
                str(item.get("excerpt") or "").strip(),
                "",
            ]
        )
    return lines


def _resolve_workdir(repo_root: Path, task: dict) -> Path:
    worktree_path = Path(str(task.get("worktree_path", "")))
    if worktree_path.is_dir():
        return worktree_path
    return repo_root


def _load_docs(task: dict, task_dir: Path) -> list[tuple[str, str]]:
    docs: list[tuple[str, str]] = []
    task_dir_relative = Path(str(task.get("task_dir", "")))
    for key, relative_path in task.get("docs", {}).items():
        if not relative_path:
            continue
        path = task_dir / relative_path
        if not path.exists():
            continue
        display_path = (task_dir_relative / relative_path).as_posix() if str(task_dir_relative) != "." else relative_path
        label = f"{key.upper()} ({display_path})"
        docs.append((label, path.read_text(encoding="utf-8")))
    return docs


def _build_task_snapshot(task: dict) -> dict[str, object]:
    return project_fields(
        task,
        {
            "id": None,
            "type": None,
            "slug": None,
            "status": None,
            "stage": None,
            "plan_status": None,
            "plan_review_round": None,
            "max_plan_review_rounds": None,
            "plan_reviewed_at": None,
            "plan_reviewed_by": None,
            "workflow_phase": None,
            "spec_status": None,
            "spec_frozen_at": None,
            "branch": None,
            "base_branch": None,
            "worktree_path": None,
            "verify_status": None,
            "subtasks": list,
            "gates": list,
            "test_strategy": dict,
            "design": dict,
            "docs": dict,
        },
    )
