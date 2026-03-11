import { useEffect, useRef, useState } from "react";
import type { ActivityEvent, ChatMessage, OfficeSubagent } from "./types";
import { toolToState, type CharacterState } from "./types";

const WS_URL =
  import.meta.env.VITE_WS_URL || "ws://localhost:8765/ws";

function deriveApiBase(url: string) {
  if (url.startsWith("ws://")) {
    return `http://${url.slice(5).replace(/\/ws$/, "")}`;
  }
  if (url.startsWith("wss://")) {
    return `https://${url.slice(6).replace(/\/ws$/, "")}`;
  }
  return url.replace(/\/ws$/, "");
}

const API_BASE = deriveApiBase(WS_URL);

export interface UseActivitySocketResult {
  lastEvent: ActivityEvent | null;
  characterState: CharacterState;
  lastTool: string | null;
  connectionStatus: "connecting" | "open" | "closed" | "error";
  chatMessages: ChatMessage[];
  subagents: OfficeSubagent[];
  sendChatCommand: (content: string, name?: string) => Promise<void>;
  spawnSubagent: (task: string, name?: string) => Promise<void>;
}

export function useActivitySocket(): UseActivitySocketResult {
  const [lastEvent, setLastEvent] = useState<ActivityEvent | null>(null);
  const [characterState, setCharacterState] = useState<CharacterState>("idle");
  const [lastTool, setLastTool] = useState<string | null>(null);
  const [connectionStatus, setConnectionStatus] = useState<
    "connecting" | "open" | "closed" | "error"
  >("connecting");
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([]);
  const [subagents, setSubagents] = useState<OfficeSubagent[]>([]);
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<number | null>(null);
  const idleTimeoutRef = useRef<number | null>(null);

  useEffect(() => {
    function connect() {
      setConnectionStatus("connecting");
      const ws = new WebSocket(WS_URL);
      wsRef.current = ws;

      ws.onopen = () => setConnectionStatus("open");
      ws.onclose = () => {
        setConnectionStatus("closed");
        wsRef.current = null;
        reconnectTimeoutRef.current = window.setTimeout(connect, 3000);
      };
      ws.onerror = () => setConnectionStatus("error");

      ws.onmessage = (ev: MessageEvent) => {
        try {
          const data = JSON.parse(ev.data as string) as ActivityEvent;
          if (data.type === "pong") return;
          setLastEvent(data);

          if (data.type === "command_queued") {
            const content =
              data.kind === "spawn_subagent"
                ? `Spawn ${data.name || "subagent"}: ${data.task || ""}`.trim()
                : data.content || "";
            if (content) {
              setChatMessages((prev) => [
                ...prev.slice(-39),
                {
                  id: `${data.id || crypto.randomUUID()}-user`,
                  role: "user",
                  content,
                  ts: data.ts || new Date().toISOString(),
                  name: data.name || "You",
                },
              ]);
            }
          }

          if (data.type === "chat_message" && (data.content || data.media?.length)) {
            const content = data.content || "";
            setChatMessages((prev) => [
              ...prev.slice(-39),
              {
                id: `${data.subagent_id || data.id || crypto.randomUUID()}-${Date.now()}`,
                role: data.role || "assistant",
                content,
                ts: data.ts || new Date().toISOString(),
                name: data.name || undefined,
                media: data.media || [],
              },
            ]);
          }

          switch (data.type) {
            case "tool_start":
              if (data.tool) {
                setLastTool(data.tool);
                setCharacterState(toolToState(data.tool));
              }
              if (idleTimeoutRef.current) {
                clearTimeout(idleTimeoutRef.current);
                idleTimeoutRef.current = null;
              }
              break;
            case "tool_end":
              // Stay in current state briefly; then idle after a short delay
              idleTimeoutRef.current = window.setTimeout(() => {
                setCharacterState("idle");
                idleTimeoutRef.current = null;
              }, 400);
              break;
            case "waiting_input":
              setCharacterState("waiting");
              setLastTool(null);
              if (idleTimeoutRef.current) {
                clearTimeout(idleTimeoutRef.current);
                idleTimeoutRef.current = null;
              }
              break;
            case "turn_end":
              idleTimeoutRef.current = window.setTimeout(() => {
                setCharacterState("idle");
                setLastTool(null);
                idleTimeoutRef.current = null;
              }, 300);
              break;
            case "subagent_start":
              setSubagents((prev) => {
                const label = data.label || data.name || `Agent ${data.id?.slice(0, 4) || "bot"}`;
                const rest = prev.filter((entry) => entry.id !== data.id);
                return [...rest, { id: data.id || crypto.randomUUID(), label, status: "running" }];
              });
              break;
            case "subagent_end":
              setSubagents((prev) =>
                prev.map((entry) =>
                  entry.id === data.id ? { ...entry, status: "complete" } : entry
                )
              );
              break;
            default:
              break;
          }
        } catch {
          // ignore parse errors
        }
      };
    }

    connect();
    return () => {
      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
        reconnectTimeoutRef.current = null;
      }
      if (idleTimeoutRef.current) {
        clearTimeout(idleTimeoutRef.current);
        idleTimeoutRef.current = null;
      }
    };
  }, []);

  async function postCommand(payload: Record<string, unknown>) {
    const response = await fetch(`${API_BASE}/commands`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(payload),
    });
    if (!response.ok) {
      throw new Error("Failed to queue command.");
    }
  }

  async function sendChatCommand(content: string, name?: string) {
    const trimmed = content.trim();
    if (!trimmed) {
      return;
    }
    await postCommand({
      kind: "chat",
      content: trimmed,
      name: name || "You",
      session_id: "office",
      sender_id: "web-ui",
      ts: new Date().toISOString(),
    });
  }

  async function spawnSubagent(task: string, name?: string) {
    const trimmed = task.trim();
    if (!trimmed) {
      return;
    }
    await postCommand({
      kind: "spawn_subagent",
      task: trimmed,
      name: name || "",
      session_id: "office",
      sender_id: "web-ui",
      ts: new Date().toISOString(),
    });
  }

  return {
    lastEvent,
    characterState,
    lastTool,
    connectionStatus,
    chatMessages,
    subagents,
    sendChatCommand,
    spawnSubagent,
  };
}
