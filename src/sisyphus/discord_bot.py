from __future__ import annotations

import asyncio
import os
from pathlib import Path

from .api import queue_conversation
from .config import SisyphusConfig
from .service import TaskNotification, TaskNotificationTracker, run_service_step


def build_discord_source_context(
    *,
    channel_id: int,
    thread_id: int | None,
    message_id: int,
    author_id: int,
    author_name: str,
) -> dict[str, object]:
    return {
        "kind": "discord",
        "channel_id": str(channel_id),
        "thread_id": str(thread_id) if thread_id is not None else None,
        "message_id": str(message_id),
        "author_id": str(author_id),
        "author_name": author_name,
    }


def queue_discord_conversation(
    repo_root: Path,
    *,
    message: str,
    channel_id: int,
    thread_id: int | None,
    message_id: int,
    author_id: int,
    author_name: str,
    title: str | None = None,
    task_type: str = "feature",
    slug: str | None = None,
    instruction: str | None = None,
    agent_id: str = "worker-1",
    role: str = "worker",
    provider: str = "codex",
    owned_paths: list[str] | None = None,
    provider_args: list[str] | None = None,
    no_run: bool = False,
) -> tuple[dict, Path]:
    queued = queue_conversation(
        repo_root=repo_root,
        message=message,
        title=title,
        task_type=task_type,
        slug=slug,
        instruction=instruction,
        agent_id=agent_id,
        role=role,
        provider=provider,
        owned_paths=owned_paths,
        provider_args=provider_args,
        source_context=build_discord_source_context(
            channel_id=channel_id,
            thread_id=thread_id,
            message_id=message_id,
            author_id=author_id,
            author_name=author_name,
        ),
        auto_run=not no_run,
    )
    return queued.event, queued.event_path


def run_discord_bot(
    repo_root: Path,
    config: SisyphusConfig,
    *,
    token: str | None,
    poll_interval_seconds: int,
    allowed_channel_ids: list[int] | None = None,
) -> int:
    discord = _require_discord()
    resolved_token = token or os.environ.get("DISCORD_BOT_TOKEN")
    if not resolved_token:
        raise RuntimeError("discord bot token is required via --token or DISCORD_BOT_TOKEN")

    intents = discord.Intents.default()
    intents.message_content = True
    intents.messages = True
    intents.guilds = True

    client_class = _build_discord_client_class(discord)
    client = client_class(
        intents=intents,
        repo_root=repo_root,
        config=config,
        poll_interval_seconds=poll_interval_seconds,
        allowed_channel_ids=allowed_channel_ids or [],
    )
    client.run(resolved_token)
    return 0


def _require_discord():
    try:
        import discord  # type: ignore
    except ImportError as exc:
        raise RuntimeError("discord.py is not installed. Install the optional discord dependency to use discord-bot.") from exc
    return discord


def _build_discord_client_class(discord):
    class SisyphusDiscordClient(discord.Client):
        def __init__(
            self,
            *,
            repo_root: Path,
            config: SisyphusConfig,
            poll_interval_seconds: int,
            allowed_channel_ids: list[int],
            **kwargs,
        ) -> None:
            super().__init__(**kwargs)
            self.repo_root = repo_root
            self.config = config
            self.poll_interval_seconds = max(poll_interval_seconds, 1)
            self.allowed_channel_ids = {int(channel_id) for channel_id in allowed_channel_ids}
            self.tracker = TaskNotificationTracker()
            self._service_task: asyncio.Task[None] | None = None

        async def setup_hook(self) -> None:
            self._service_task = asyncio.create_task(self._service_loop())

        async def on_ready(self) -> None:
            print(f"discord ready: {self.user}")

        async def on_message(self, message) -> None:
            if message.author == self.user or getattr(message.author, "bot", False):
                return
            if not self._is_allowed_channel(message.channel):
                return
            content = (message.content or "").strip()
            if not content:
                return

            event, _ = await asyncio.to_thread(
                queue_discord_conversation,
                self.repo_root,
                message=content,
                channel_id=int(message.channel.id),
                thread_id=_thread_id_for_channel(message.channel),
                message_id=int(message.id),
                author_id=int(message.author.id),
                author_name=str(message.author),
            )
            await message.reply(f"Queued `{event['id']}`. Sisyphus is working on it.", mention_author=False)

        async def _service_loop(self) -> None:
            await self.wait_until_ready()
            while not self.is_closed():
                result = await asyncio.to_thread(
                    run_service_step,
                    self.repo_root,
                    self.config,
                    tracker=self.tracker,
                )
                for notification in result.notifications:
                    await self._send_notification(notification)
                if not result.progressed:
                    await asyncio.sleep(self.poll_interval_seconds)

        async def _send_notification(self, notification: TaskNotification) -> None:
            context = notification.source_context
            if context.get("kind") != "discord":
                return
            target_id = context.get("thread_id") or context.get("channel_id")
            if not target_id:
                return
            channel = self.get_channel(int(target_id))
            if channel is None:
                channel = await self.fetch_channel(int(target_id))
            if channel is None:
                return
            await channel.send(notification.summary)

        def _is_allowed_channel(self, channel) -> bool:
            if not self.allowed_channel_ids:
                return True
            channel_id = int(getattr(channel, "id", 0))
            parent_id = int(getattr(getattr(channel, "parent", None), "id", 0) or 0)
            return channel_id in self.allowed_channel_ids or parent_id in self.allowed_channel_ids

    return SisyphusDiscordClient


def _thread_id_for_channel(channel) -> int | None:
    parent = getattr(channel, "parent", None)
    if parent is None:
        return None
    return int(getattr(channel, "id"))
