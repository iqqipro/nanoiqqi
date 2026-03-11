"""Activity events for agent observability (Brain Office).

Contract: same event types and JSON shape are used by nanobot (emitter) and
Brain Office backend (consumer). All events have "type" and "ts" (ISO8601).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


def _iso_ts() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class ActivityEvent:
    """Base for activity events. Serialize with to_dict() then json.dumps()."""

    def to_dict(self) -> dict[str, Any]:
        raise NotImplementedError


@dataclass
class ToolStartEvent(ActivityEvent):
    type: str = "tool_start"
    tool: str = ""
    ts: str = field(default_factory=_iso_ts)
    session_id: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {"type": self.type, "tool": self.tool, "ts": self.ts, "session_id": self.session_id}


@dataclass
class ToolEndEvent(ActivityEvent):
    type: str = "tool_end"
    tool: str = ""
    ts: str = field(default_factory=_iso_ts)
    session_id: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {"type": self.type, "tool": self.tool, "ts": self.ts, "session_id": self.session_id}


@dataclass
class WaitingInputEvent(ActivityEvent):
    type: str = "waiting_input"
    ts: str = field(default_factory=_iso_ts)
    session_id: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {"type": self.type, "ts": self.ts, "session_id": self.session_id}


@dataclass
class TurnEndEvent(ActivityEvent):
    type: str = "turn_end"
    ts: str = field(default_factory=_iso_ts)
    session_id: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {"type": self.type, "ts": self.ts, "session_id": self.session_id}


@dataclass
class SubagentStartEvent(ActivityEvent):
    type: str = "subagent_start"
    id: str = ""
    label: str = ""
    parent_session_id: str = ""
    ts: str = field(default_factory=_iso_ts)

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.type,
            "id": self.id,
            "label": self.label,
            "parent_session_id": self.parent_session_id,
            "ts": self.ts,
        }


@dataclass
class SubagentEndEvent(ActivityEvent):
    type: str = "subagent_end"
    id: str = ""
    label: str = ""
    ts: str = field(default_factory=_iso_ts)

    def to_dict(self) -> dict[str, Any]:
        return {"type": self.type, "id": self.id, "label": self.label, "ts": self.ts}
