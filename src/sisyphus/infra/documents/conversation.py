from __future__ import annotations

from pathlib import Path

from ...application.ports.workflow import TaskRecord
from ...domain.task.documents import (
    render_brief,
    render_feature_plan,
    render_issue_fix_plan,
    render_issue_repro,
    single_line,
)


class RepositoryConversationDocuments:
    def materialize(
        self,
        task: TaskRecord,
        *,
        title: str,
        message: str,
        requested_slug: str,
        parent_task_id: str | None,
    ) -> None:
        repo_root = Path(str(task["repo_root"]))
        task_dir = repo_root / str(task["task_dir"])
        title_line = title or _title_from_message(message)

        brief_path = task_dir / str(task["docs"]["brief"])
        brief_path.write_text(
            render_brief(
                task,
                title_line,
                message,
                requested_slug=requested_slug,
                parent_task_id=parent_task_id,
            ),
            encoding="utf-8",
        )
        if task["type"] == "feature":
            plan_path = task_dir / str(task["docs"]["plan"])
            plan_path.write_text(
                render_feature_plan(task, title_line, message),
                encoding="utf-8",
            )
            return

        repro_path = task_dir / str(task["docs"]["repro"])
        repro_path.write_text(
            render_issue_repro(task, title_line, message),
            encoding="utf-8",
        )
        fix_plan_path = task_dir / str(task["docs"]["fix_plan"])
        fix_plan_path.write_text(
            render_issue_fix_plan(task, title_line, message),
            encoding="utf-8",
        )

    def append_log_note(self, task: TaskRecord, note: str) -> None:
        repo_root = Path(str(task["repo_root"]))
        task_dir = repo_root / str(task["task_dir"])
        log_relative = task.get("docs", {}).get("log")
        if not log_relative:
            return
        log_path = task_dir / str(log_relative)
        if not log_path.exists():
            return
        lines = log_path.read_text(encoding="utf-8").splitlines()
        try:
            index = lines.index("## Notes")
        except ValueError:
            log_path.write_text(
                log_path.read_text(encoding="utf-8").rstrip()
                + f"\n\n## Notes\n\n- {note}\n",
                encoding="utf-8",
            )
            return

        insertion_index = index + 1
        while insertion_index < len(lines) and not lines[insertion_index].startswith("## "):
            insertion_index += 1
        lines[insertion_index:insertion_index] = ["", f"- {note}"]
        log_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def _title_from_message(message: str) -> str:
    line = single_line(message)
    return line[:72] or "Conversation Task"


__all__ = ["RepositoryConversationDocuments"]
