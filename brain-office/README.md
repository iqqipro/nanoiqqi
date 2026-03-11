# Brain Office

A small web app that shows your nanobot agent as a character in a pixel-art office. The character state updates in real time based on agent activity (reading files, typing, running commands, waiting for input).

Inspired by [pixel-agents](https://github.com/pablodelucca/pixel-agents); integrated with this repo’s agent (nanobot). **Brain Office is always on**: the agent always sends activity events; you only configure the backend URL if it’s not the default.

## Architecture

- **nanobot** emits activity events (tool_start, tool_end, waiting_input, turn_end, subagent_start/end) to Brain Office (always enabled).
- **Brain Office backend** (FastAPI) receives events via `POST /events` and broadcasts them to web clients over **WebSocket** (`/ws`).
- **Frontend** (React + Vite + TypeScript) connects to the WebSocket and drives a 2D grid with a single character whose state reflects the current activity.

## Event contract

Events are JSON objects. Nanobot sends them to `{BRAIN_OFFICE_URL}/events` (default `http://localhost:8765/events`).

| type           | fields               | description                    |
|----------------|----------------------|--------------------------------|
| tool_start     | tool, ts, session_id | Agent started a tool           |
| tool_end       | tool, ts, session_id | Tool finished                  |
| waiting_input  | ts, session_id       | Agent waiting for user message |
| turn_end       | ts, session_id       | Turn finished                  |
| subagent_start | id, parent_session_id, ts | Subagent started          |
| subagent_end   | id, ts               | Subagent finished              |

## How to run

### 1. Backend (required)

From the repo root you can install the optional backend deps:

```bash
pip install -e ".[brain-office]"
```

Then run the backend from the backend directory:

```bash
cd brain-office/backend
uvicorn app:app --reload --port 8765
```

Or install deps only in the backend folder:

```bash
cd brain-office/backend
pip install -r requirements.txt
uvicorn app:app --reload --port 8765
```

### 2. Frontend (dev)

```bash
cd brain-office/frontend
npm install
npm run dev
```

Open http://localhost:5173 . The app will connect to `ws://localhost:8765/ws` by default. Override with `VITE_WS_URL=ws://host:port/ws` if needed.

### 3. Nanobot

The agent **always** sends activity to Brain Office. Default URL is `http://localhost:8765`. To override (e.g. when running in Docker), set in `~/.nanobot/config.json`:

```json
{
  "brainOffice": {
    "url": "http://localhost:8765"
  }
}
```

When the agent runs in Docker with `docker compose run --rm nanobot-cli agent`, the URL is already set in `docker-compose.yml`; you don't need to add this to config. If you run the agent in a different way (e.g. custom container), set the URL to `http://brain-office:8765` or use `NANOBOT_BRAIN_OFFICE__URL=http://brain-office:8765`.

Then run the agent (e.g. `nanobot agent`). Activity will be sent to the backend and the Brain Office UI will update in real time.

## Docker (all-in-one)

From the repo root you can run Brain Office (backend + frontend) and nanobot in Docker:

```bash
# Build and start Brain Office (UI + backend on port 8765)
docker compose build brain-office
docker compose up -d brain-office
```

Open **http://localhost:8765** in your browser to see the UI.

When you run the agent with the same Compose stack, the URL is already set in `docker-compose.yml` (`NANOBOT_BRAIN_OFFICE__URL=http://brain-office:8765`), so you don't need to add anything to `~/.nanobot/config.json`. Just run:

```bash
docker compose run --rm nanobot-cli agent
```

Events will flow from the agent container to the `brain-office` service; the UI at http://localhost:8765 updates in real time.

## Production (single port)

Build the frontend and serve it from the backend:

```bash
cd brain-office/frontend
npm run build
```

Then start the backend from the repo root (so `frontend/dist` is next to `backend/`). The FastAPI app will serve the built files at `/` and still expose `/events` and `/ws`.

## Character states

| State    | When                         | Visual (v1) |
|---------|------------------------------|-------------|
| idle    | No recent event / turn_end   | ·           |
| reading | read_file, list_dir, web_*   | 📖          |
| typing  | write_file, edit_file        | ✎           |
| running | exec                         | ▶           |
| waiting | waiting_input                | …           |

## Folder layout

```
brain-office/
  backend/       # FastAPI app (POST /events, WebSocket /ws)
  frontend/     # React + Vite + TypeScript
  README.md     # This file
```

## Not in v1

- Editor for office layout (walls, furniture, save/load)
- Pathfinding; multiple characters/desks
- Sound or notifications
- Paid tilesets (use placeholders or free assets)
