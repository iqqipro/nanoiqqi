"""Bridge between Brain Office web UI and the agent message bus."""

from __future__ import annotations

import asyncio
import base64
import mimetypes
from datetime import datetime, timezone
from pathlib import Path
from typing import Awaitable, Callable

import httpx
from loguru import logger

from nanobot.bus.events import InboundMessage, OutboundMessage
from nanobot.bus.queue import MessageBus


def _iso_ts() -> str:
    return datetime.now(timezone.utc).isoformat()


class BrainOfficeBridge:
    """Poll commands from Brain Office and publish agent replies back to the UI."""

    def __init__(
        self,
        bus: MessageBus,
        base_url: str,
        *,
        sender_id: str = "brain-office-ui",
        spawn_callback: Callable[[str, str | None, str], Awaitable[str]] | None = None,
        poll_interval_seconds: float = 1.0,
    ) -> None:
        self._bus = bus
        self._base_url = base_url.rstrip("/")
        self._sender_id = sender_id
        self._spawn_callback = spawn_callback
        self._poll_interval_seconds = poll_interval_seconds
        self._running = False
        self._client: httpx.AsyncClient | None = None

    async def _http(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=5.0)
        return self._client

    async def _upload_media(self, media_paths: list[str]) -> list[str]:
        client = await self._http()
        uploaded_urls: list[str] = []

        for media_path in media_paths:
            if media_path.startswith(("http://", "https://", "data:")):
                uploaded_urls.append(media_path)
                continue

            try:
                path = Path(media_path).expanduser().resolve()
                if not path.is_file():
                    continue

                mime_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
                response = await client.post(
                    f"{self._base_url}/uploads",
                    json={
                        "filename": path.name,
                        "mime_type": mime_type,
                        "content_base64": base64.b64encode(path.read_bytes()).decode("ascii"),
                    },
                )
                if response.status_code >= 400:
                    continue

                payload = response.json()
                media = payload.get("media") if isinstance(payload, dict) else None
                url = media.get("url") if isinstance(media, dict) else None
                if isinstance(url, str) and url:
                    # Use relative path so the frontend (same origin, e.g. localhost:8765) can open the file.
                    # Absolute URLs like http://brain-office:8765/uploads/... are not reachable from the user's browser.
                    uploaded_urls.append(url if url.startswith("/") else f"{self._base_url}{url}")
            except Exception as exc:
                logger.debug("Brain Office media upload failed for {}: {}", media_path, exc)

        return uploaded_urls

    async def dispatch_outbound(self, msg: OutboundMessage) -> None:
        """Send an outbound agent message to Brain Office."""
        if msg.channel != "brain-office":
            return

        client = await self._http()
        metadata = dict(msg.metadata or {})
        role = "progress" if metadata.get("_progress") else "assistant"
        uploaded_media = await self._upload_media(list(msg.media or []))
        try:
            await client.post(
                f"{self._base_url}/messages",
                json={
                    "type": "chat_message",
                    "role": role,
                    "content": msg.content,
                    "media": uploaded_media,
                    "session_id": msg.chat_id,
                    "metadata": metadata,
                    "ts": _iso_ts(),
                },
            )
        except Exception as exc:
            logger.debug("Brain Office outbound dispatch failed: {}", exc)

    async def _handle_command(self, command: dict) -> None:
        kind = str(command.get("kind") or "chat").strip().lower()
        chat_id = str(command.get("session_id") or "office")

        if kind == "spawn_subagent":
            task = str(command.get("task") or "").strip()
            label = str(command.get("name") or "").strip() or None
            if not task:
                return
            if self._spawn_callback is not None:
                status = await self._spawn_callback(task, label, chat_id)
                client = await self._http()
                await client.post(
                    f"{self._base_url}/messages",
                    json={
                        "type": "chat_message",
                        "role": "system",
                        "content": status,
                        "session_id": chat_id,
                        "name": label or "",
                        "ts": _iso_ts(),
                    },
                )
                return

        content = str(command.get("content") or "").strip()
        if not content:
            return

        await self._bus.publish_inbound(
            InboundMessage(
                channel="brain-office",
                sender_id=str(command.get("sender_id") or self._sender_id),
                chat_id=chat_id,
                content=content,
                metadata={"command_id": command.get("id", "")},
            )
        )

    async def run(self) -> None:
        """Start polling Brain Office for incoming commands."""
        self._running = True
        client = await self._http()

        while self._running:
            try:
                response = await client.get(f"{self._base_url}/commands/next")
                if response.status_code == 204:
                    await asyncio.sleep(self._poll_interval_seconds)
                    continue
                if response.status_code >= 400:
                    await asyncio.sleep(self._poll_interval_seconds)
                    continue
                payload = response.json()
                if isinstance(payload, dict):
                    await self._handle_command(payload)
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.debug("Brain Office command poll failed: {}", exc)
                await asyncio.sleep(self._poll_interval_seconds)

    async def aclose(self) -> None:
        self._running = False
        if self._client is not None:
            try:
                await self._client.aclose()
            except Exception:
                pass
            self._client = None
