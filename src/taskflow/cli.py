from __future__ import annotations

import argparse
import json
from pathlib import Path

from .audit import run_verify
from .closeout import run_close
from .config import load_config
from .discovery import detect_repo_root
from .state import create_task_record, list_task_records
from .templates import materialize_task_templates


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="taskflow")
    subparsers = parser.add_subparsers(dest="command", required=True)

    new_parser = subparsers.add_parser("new")
    new_subparsers = new_parser.add_subparsers(dest="task_type", required=True)

    feature_parser = new_subparsers.add_parser("feature")
    feature_parser.add_argument("slug")

    issue_parser = new_subparsers.add_parser("issue")
    issue_parser.add_argument("slug")

    verify_parser = subparsers.add_parser("verify")
    verify_parser.add_argument("task_id")

    close_parser = subparsers.add_parser("close")
    close_parser.add_argument("task_id")
    close_parser.add_argument("--allow-dirty", action="store_true")

    status_parser = subparsers.add_parser("status")
    status_parser.add_argument("--json", action="store_true")
    status_parser.add_argument("--open", dest="only_open", action="store_true")
    status_parser.add_argument("--blocked", dest="only_blocked", action="store_true")

    return parser


def handle_new(task_type: str, slug: str) -> int:
    repo_root = detect_repo_root(Path.cwd())
    config = load_config(repo_root)
    task = create_task_record(repo_root=repo_root, config=config, task_type=task_type, slug=slug)
    materialize_task_templates(task)
    print(f"created {task['id']}")
    print(f"task_dir: {task['task_dir']}")
    print(f"branch: {task['branch']}")
    print(f"worktree_path: {task['worktree_path']}")
    return 0


def handle_verify(task_id: str) -> int:
    repo_root = detect_repo_root(Path.cwd())
    config = load_config(repo_root)
    outcome = run_verify(repo_root=repo_root, config=config, task_id=task_id)
    print(f"verified {outcome.task_id}")
    print(f"status: {outcome.status}")
    print(f"audit_attempts: {outcome.audit_attempts}/{outcome.max_audit_attempts}")
    print(f"verify_file: {outcome.verify_file}")
    if outcome.gates:
        print("gates:")
        for gate in outcome.gates:
            print(f"- {gate['code']}: {gate['message']}")
        return 1
    print("gates: none")
    return 0


def handle_close(task_id: str, allow_dirty: bool) -> int:
    repo_root = detect_repo_root(Path.cwd())
    config = load_config(repo_root)
    outcome = run_close(repo_root=repo_root, config=config, task_id=task_id, allow_dirty=allow_dirty)
    print(f"close {outcome.task_id}")
    print(f"status: {outcome.status}")
    print(f"closed: {'yes' if outcome.closed else 'no'}")
    if outcome.gates:
        print("gates:")
        for gate in outcome.gates:
            print(f"- {gate['code']}: {gate['message']}")
        return 1
    print("gates: none")
    return 0


def handle_status(as_json: bool, only_open: bool, only_blocked: bool) -> int:
    repo_root = detect_repo_root(Path.cwd())
    config = load_config(repo_root)
    tasks = list_task_records(repo_root=repo_root, task_dir_name=config.task_dir)

    if only_open:
        tasks = [task for task in tasks if task.get("status") in {"open", "in_progress"}]
    if only_blocked:
        tasks = [task for task in tasks if task.get("status") == "blocked"]

    tasks = sorted(
        tasks,
        key=lambda task: (
            task.get("updated_at", ""),
            task.get("created_at", ""),
            task.get("id", ""),
        ),
        reverse=True,
    )

    if as_json:
        print(json.dumps(tasks, indent=2))
        return 0

    if not tasks:
        print("no tasks found")
        return 0

    for task in tasks:
        gate_count = len(task.get("gates", []))
        print(
            f"{task.get('id')} "
            f"[{task.get('type')}] "
            f"status={task.get('status')} "
            f"stage={task.get('stage')} "
            f"audit={task.get('audit_attempts', 0)}/{task.get('max_audit_attempts', 10)} "
            f"gates={gate_count}"
        )
        if gate_count:
            for gate in task["gates"]:
                print(f"  - {gate.get('code')}: {gate.get('message')}")
    return 0


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "new":
        return handle_new(task_type=args.task_type, slug=args.slug)
    if args.command == "verify":
        return handle_verify(task_id=args.task_id)
    if args.command == "close":
        return handle_close(task_id=args.task_id, allow_dirty=args.allow_dirty)
    if args.command == "status":
        return handle_status(
            as_json=args.json,
            only_open=args.only_open,
            only_blocked=args.only_blocked,
        )

    parser.error("unknown command")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
