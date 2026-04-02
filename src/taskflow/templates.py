from __future__ import annotations

from pathlib import Path


def template_root() -> Path:
    return Path(__file__).resolve().parents[2] / "templates"


def materialize_task_templates(task: dict) -> None:
    repo_root = Path(task["repo_root"])
    task_dir = repo_root / task["task_dir"]
    kind = task["type"]
    source_root = template_root() / kind

    for template_file in source_root.iterdir():
        if not template_file.is_file():
            continue
        target = task_dir / template_file.name
        content = template_file.read_text(encoding="utf-8")
        content = content.replace("{{TASK_ID}}", task["id"])
        content = content.replace("{{TASK_TYPE}}", task["type"])
        content = content.replace("{{SLUG}}", task["slug"])
        content = content.replace("{{BRANCH}}", task["branch"])
        target.write_text(content, encoding="utf-8")
