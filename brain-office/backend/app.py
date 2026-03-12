"""
Brain Office backend: receives activity events from nanoiqqi (POST /events)
and broadcasts them to web clients over WebSocket (/ws).
"""

from __future__ import annotations

import asyncio
import base64
import json
import mimetypes
import uuid
from collections import deque
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request, Response, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

app = FastAPI(title="Brain Office", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# All connected WebSocket clients
_connections: list[WebSocket] = []
_broadcast_lock = asyncio.Lock()
_command_queue: deque[dict[str, Any]] = deque()
_command_lock = asyncio.Lock()
_uploads_dir = Path(__file__).resolve().parent.parent / "uploads"
_uploads_dir.mkdir(parents=True, exist_ok=True)


async def _broadcast(payload: dict[str, Any]) -> None:
    """Send payload as JSON to all connected WebSocket clients."""
    text = json.dumps(payload, ensure_ascii=False)
    dead: list[WebSocket] = []
    async with _broadcast_lock:
        for ws in _connections:
            try:
                await ws.send_text(text)
            except Exception:
                dead.append(ws)
        for ws in dead:
            if ws in _connections:
                _connections.remove(ws)


async def _enqueue_command(payload: dict[str, Any]) -> dict[str, Any]:
    async with _command_lock:
        command = {
            "id": payload.get("id") or str(uuid.uuid4())[:8],
            "kind": payload.get("kind") or "chat",
            "session_id": payload.get("session_id") or "office",
            "sender_id": payload.get("sender_id") or "web-ui",
            "name": payload.get("name") or "",
            "content": payload.get("content") or "",
            "task": payload.get("task") or "",
            "ts": payload.get("ts"),
        }
        _command_queue.append(command)
        return command


async def _next_command() -> dict[str, Any] | None:
    async with _command_lock:
        if not _command_queue:
            return None
        return _command_queue.popleft()


def _save_uploaded_media(
    *,
    filename: str,
    content_base64: str,
    mime_type: str | None = None,
) -> dict[str, str]:
    suffix = Path(filename).suffix or mimetypes.guess_extension(mime_type or "") or ".bin"
    safe_name = f"{uuid.uuid4().hex[:12]}{suffix}"
    file_path = _uploads_dir / safe_name
    data = base64.b64decode(content_base64)
    file_path.write_bytes(data)
    return {
        "url": f"/uploads/{safe_name}",
        "filename": safe_name,
        "mime_type": mime_type or mimetypes.guess_type(filename)[0] or "application/octet-stream",
    }


@app.post("/events")
async def post_event(request: Request) -> JSONResponse:
    """
    Receive a single activity event from nanoiqqi (HTTP POST).
    Body must be a JSON object with at least "type" and "ts".
    The event is broadcast to all connected WebSocket clients.
    """
    try:
        event = await request.json()
    except Exception:
        return JSONResponse(
            content={"error": "Invalid JSON body"},
            status_code=400,
        )
    if not isinstance(event, dict) or "type" not in event:
        return JSONResponse(
            content={"error": "Invalid event: expected JSON object with 'type'"},
            status_code=400,
        )
    await _broadcast(event)
    return JSONResponse(content={"ok": True})


@app.post("/commands")
async def post_command(request: Request) -> JSONResponse:
    """Receive a user command from the Brain Office UI."""
    try:
        payload = await request.json()
    except Exception:
        return JSONResponse(content={"error": "Invalid JSON body"}, status_code=400)

    if not isinstance(payload, dict):
        return JSONResponse(content={"error": "Expected JSON object"}, status_code=400)

    kind = (payload.get("kind") or "chat").strip().lower()
    if kind not in {"chat", "spawn_subagent"}:
        return JSONResponse(content={"error": "Unsupported command kind"}, status_code=400)

    if kind == "chat" and not str(payload.get("content") or "").strip():
        return JSONResponse(content={"error": "content is required"}, status_code=400)

    if kind == "spawn_subagent" and not str(payload.get("task") or "").strip():
        return JSONResponse(content={"error": "task is required"}, status_code=400)

    command = await _enqueue_command(payload)
    await _broadcast(
        {
            "type": "command_queued",
            "id": command["id"],
            "kind": command["kind"],
            "session_id": command["session_id"],
            "sender_id": command["sender_id"],
            "name": command["name"],
            "content": command["content"],
            "task": command["task"],
        }
    )
    return JSONResponse(content={"ok": True, "command": command})


@app.get("/commands/next", response_model=None)
async def get_next_command() -> Response | JSONResponse:
    """Agent bridge polls this endpoint to receive queued UI commands."""
    command = await _next_command()
    if command is None:
        return Response(status_code=204)
    return JSONResponse(content=command)


@app.post("/messages")
async def post_message(request: Request) -> JSONResponse:
    """Receive agent responses/progress and broadcast them to the UI."""
    try:
        payload = await request.json()
    except Exception:
        return JSONResponse(content={"error": "Invalid JSON body"}, status_code=400)

    if not isinstance(payload, dict):
        return JSONResponse(content={"error": "Invalid JSON body"}, status_code=400)

    content = str(payload.get("content") or "").strip()
    media = payload.get("media") or []
    if not content and not media:
        return JSONResponse(content={"error": "content or media is required"}, status_code=400)

    event = {
        "type": payload.get("type") or "chat_message",
        "role": payload.get("role") or "assistant",
        "content": content,
        "session_id": payload.get("session_id") or "office",
        "name": payload.get("name") or "",
        "subagent_id": payload.get("subagent_id") or "",
        "ts": payload.get("ts"),
        "media": media,
        "metadata": payload.get("metadata") or {},
    }
    await _broadcast(event)
    return JSONResponse(content={"ok": True})


@app.post("/uploads")
async def post_upload(request: Request) -> JSONResponse:
    """Receive uploaded media from the agent bridge and store it locally."""
    try:
        payload = await request.json()
    except Exception:
        return JSONResponse(content={"error": "Invalid JSON body"}, status_code=400)

    if not isinstance(payload, dict):
        return JSONResponse(content={"error": "Expected JSON object"}, status_code=400)

    filename = str(payload.get("filename") or "").strip()
    content_base64 = str(payload.get("content_base64") or "").strip()
    if not filename or not content_base64:
        return JSONResponse(
            content={"error": "filename and content_base64 are required"},
            status_code=400,
        )

    uploaded = _save_uploaded_media(
        filename=filename,
        content_base64=content_base64,
        mime_type=str(payload.get("mime_type") or "").strip() or None,
    )
    return JSONResponse(content={"ok": True, "media": uploaded})


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    """WebSocket: clients receive every event that is POSTed to /events."""
    await websocket.accept()
    async with _broadcast_lock:
        _connections.append(websocket)
    try:
        while True:
            # Keep connection alive; we don't expect client messages
            data = await websocket.receive_text()
            # Optional: echo or ignore; for now just keep reading
            if data.strip().lower() == "ping":
                await websocket.send_text(json.dumps({"type": "pong"}))
    except WebSocketDisconnect:
        pass
    finally:
        async with _broadcast_lock:
            if websocket in _connections:
                _connections.remove(websocket)


@app.get("/health")
async def health() -> dict[str, str]:
    """Health check."""
    return {"status": "ok"}


# Optional: serve frontend build in production (mount after routes)
_dist = Path(__file__).resolve().parent.parent / "frontend" / "dist"
app.mount("/uploads", StaticFiles(directory=str(_uploads_dir)), name="uploads")
if _dist.is_dir():
    app.mount("/", StaticFiles(directory=str(_dist), html=True), name="static")

