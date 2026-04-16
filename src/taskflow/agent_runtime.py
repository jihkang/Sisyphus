from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import subprocess
import sys
import threading

from .agents import AgentTrackingError, register_agent, update_agent
from .config import SisyphusConfig


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
    config: SisyphusConfig,
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
    env: dict[str, str] | None = None,
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

    try:
        process = subprocess.Popen(
            command,
            cwd=run_cwd or Path.cwd(),
            env=_build_process_env(env),
            stdin=subprocess.PIPE if stdin_text is not None else None,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
    )
    except OSError as exc:
        update_agent(
            repo_root=repo_root,
            config=config,
            task_id=task_id,
            agent_id=agent_id,
            status="failed",
            provider=provider,
            command=command,
            error=str(exc),
            last_message_summary=str(exc),
        )
        raise AgentTrackingError(str(exc)) from exc

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
            _write_stdout_line(line)
    finally:
        process.stdout.close()


def _heartbeat_loop(
    *,
    stop_event: threading.Event,
    repo_root: Path,
    config: SisyphusConfig,
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


def _build_process_env(overrides: dict[str, str] | None) -> dict[str, str]:
    env = dict(os.environ)
    if overrides:
        env.update(overrides)
    return env


def _write_stdout_line(line: str) -> None:
    try:
        sys.stdout.write(line)
        sys.stdout.flush()
    except UnicodeEncodeError:
        encoding = getattr(sys.stdout, "encoding", None) or "utf-8"
        if hasattr(sys.stdout, "buffer"):
            sys.stdout.buffer.write(line.encode(encoding, errors="replace"))
            sys.stdout.flush()
            return
        sys.stdout.write(line.encode(encoding, errors="replace").decode(encoding, errors="replace"))
        sys.stdout.flush()
