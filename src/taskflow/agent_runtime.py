from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import subprocess
import sys
import threading

from .agents import AgentTrackingError, register_agent, update_agent
from .config import TaskflowConfig


@dataclass(slots=True)
class AgentRunOutcome:
    task_id: str
    agent_id: str
    exit_code: int
    status: str


class OutputTracker:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._lines: list[str] = []

    def add_line(self, line: str) -> None:
        cleaned = line.strip()
        if not cleaned:
            return
        with self._lock:
            self._lines.append(cleaned)
            self._lines = self._lines[-10:]

    def summary(self) -> str | None:
        with self._lock:
            if not self._lines:
                return None
            recent = self._lines[-3:]
        joined = " | ".join(recent)
        return joined[-240:]


def run_tracked_agent(
    repo_root: Path,
    config: TaskflowConfig,
    task_id: str,
    agent_id: str,
    role: str,
    provider: str,
    command: list[str],
    *,
    current_step: str | None = None,
    last_message_summary: str | None = None,
    owned_paths: list[str] | None = None,
    heartbeat_seconds: int = 10,
    run_cwd: Path | None = None,
    stdin_text: str | None = None,
) -> AgentRunOutcome:
    if not command:
        raise AgentTrackingError("agent run requires a command after `--`")

    step = current_step or f"running {' '.join(command)}"
    initial_summary = last_message_summary or f"{provider} wrapper started"
    register_agent(
        repo_root=repo_root,
        config=config,
        task_id=task_id,
        agent_id=agent_id,
        role=role,
        provider=provider,
        current_step=step,
        last_message_summary=initial_summary,
        owned_paths=owned_paths,
        command=command,
        status="running",
    )

    process = subprocess.Popen(
        command,
        cwd=run_cwd or Path.cwd(),
        stdin=subprocess.PIPE if stdin_text is not None else None,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )

    tracker = OutputTracker()
    output_thread = threading.Thread(
        target=_stream_output,
        kwargs={"process": process, "tracker": tracker},
        daemon=True,
    )
    output_thread.start()

    if stdin_text is not None and process.stdin is not None:
        process.stdin.write(stdin_text)
        process.stdin.close()

    update_agent(
        repo_root=repo_root,
        config=config,
        task_id=task_id,
        agent_id=agent_id,
        pid=process.pid,
        command=command,
        provider=provider,
        current_step=step,
        last_message_summary=initial_summary,
    )

    stop_event = threading.Event()
    heartbeat_thread = threading.Thread(
        target=_heartbeat_loop,
        kwargs={
            "stop_event": stop_event,
            "repo_root": repo_root,
            "config": config,
            "task_id": task_id,
            "agent_id": agent_id,
            "provider": provider,
            "command": command,
            "current_step": step,
            "initial_summary": initial_summary,
            "heartbeat_seconds": heartbeat_seconds,
            "tracker": tracker,
        },
        daemon=True,
    )
    heartbeat_thread.start()

    try:
        exit_code = process.wait()
    except KeyboardInterrupt:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
        stop_event.set()
        output_thread.join(timeout=heartbeat_seconds + 1)
        heartbeat_thread.join(timeout=heartbeat_seconds + 1)
        update_agent(
            repo_root=repo_root,
            config=config,
            task_id=task_id,
            agent_id=agent_id,
            status="cancelled",
            provider=provider,
            command=command,
            error="cancelled by operator",
            last_message_summary="cancelled by operator",
        )
        raise

    stop_event.set()
    output_thread.join(timeout=heartbeat_seconds + 1)
    heartbeat_thread.join(timeout=heartbeat_seconds + 1)

    status = "completed" if exit_code == 0 else "failed"
    error = None if exit_code == 0 else f"command exited with code {exit_code}"
    final_summary = tracker.summary()
    if not final_summary:
        final_summary = (
            "wrapper finished successfully"
            if exit_code == 0 else
            f"wrapper failed with exit code {exit_code}"
        )
    update_agent(
        repo_root=repo_root,
        config=config,
        task_id=task_id,
        agent_id=agent_id,
        status=status,
        provider=provider,
        command=command,
        error=error,
        last_message_summary=final_summary,
    )
    return AgentRunOutcome(
        task_id=task_id,
        agent_id=agent_id,
        exit_code=exit_code,
        status=status,
    )


def _stream_output(*, process: subprocess.Popen[str], tracker: OutputTracker) -> None:
    if process.stdout is None:
        return
    try:
        for line in process.stdout:
            tracker.add_line(line)
            sys.stdout.write(line)
            sys.stdout.flush()
    finally:
        process.stdout.close()


def _heartbeat_loop(
    *,
    stop_event: threading.Event,
    repo_root: Path,
    config: TaskflowConfig,
    task_id: str,
    agent_id: str,
    provider: str,
    command: list[str],
    current_step: str,
    initial_summary: str,
    heartbeat_seconds: int,
    tracker: OutputTracker,
) -> None:
    while not stop_event.wait(max(1, heartbeat_seconds)):
        try:
            update_agent(
                repo_root=repo_root,
                config=config,
                task_id=task_id,
                agent_id=agent_id,
                provider=provider,
                command=command,
                current_step=current_step,
                last_message_summary=tracker.summary() or initial_summary,
            )
        except (AgentTrackingError, FileNotFoundError):
            return
