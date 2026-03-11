"""Activity sink: export of agent events to Brain Office.

If the backend is unavailable, the agent continues normally (fail silently or log warning).
"""

from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

from loguru import logger

from nanobot.agent.activity_events import ActivityEvent

if TYPE_CHECKING:
    pass


class ActivitySink(ABC):
    """Abstract sink for activity events."""

    @abstractmethod
    async def emit(self, event: ActivityEvent) -> None:
        """Send one activity event. Must not raise; failures are logged."""
        ...


class NoOpActivitySink(ActivitySink):
    """Sink that discards all events."""

    async def emit(self, event: ActivityEvent) -> None:
        pass


class HttpActivitySink(ActivitySink):
    """Sink that POSTs events as JSON to a URL (Brain Office backend)."""

    def __init__(self, url: str, timeout_seconds: float = 2.0) -> None:
        self._url = url.rstrip("/")
        self._timeout = timeout_seconds
        self._session: Any = None

    async def _client(self):
        if self._session is None:
            try:
                import httpx
                self._session = httpx.AsyncClient(timeout=self._timeout)
            except ImportError:
                logger.warning("httpx not available; Brain Office activity sink disabled")
                return None
        return self._session

    async def emit(self, event: ActivityEvent) -> None:
        client = await self._client()
        if client is None:
            return
        try:
            r = await client.post(
                f"{self._url}/events",
                json=event.to_dict(),
            )
            if r.status_code >= 400:
                logger.debug("Activity sink POST failed: {} {}", r.status_code, r.text[:200])
        except Exception as e:
            logger.debug("Activity sink error (non-fatal): {}", e)

    async def aclose(self) -> None:
        if self._session is not None:
            try:
                await self._session.aclose()
            except Exception:
                pass
            self._session = None


def make_activity_sink(url: str | None) -> ActivitySink:
    """Build an activity sink. Returns NoOp if URL empty; otherwise POSTs to url/events."""
    if not (url or "").strip():
        return NoOpActivitySink()
    u = url.strip()
    if not u.startswith("http://") and not u.startswith("https://"):
        logger.warning("Brain Office URL should be http(s)://; got {}", u[:50])
    return HttpActivitySink(u)
