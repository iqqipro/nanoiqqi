/** Activity event from nanoiqqi (same contract as backend). */
export interface ActivityEvent {
  type: string;
  ts?: string;
  session_id?: string;
  tool?: string;
  id?: string;
  parent_session_id?: string;
  label?: string;
  role?: "user" | "assistant" | "progress" | "system";
  content?: string;
  kind?: "chat" | "spawn_subagent";
  name?: string;
  task?: string;
  subagent_id?: string;
  media?: string[];
  metadata?: Record<string, unknown>;
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant" | "progress" | "system";
  content: string;
  ts: string;
  name?: string;
  media?: string[];
}

export interface OfficeSubagent {
  id: string;
  label: string;
  status: "running" | "complete";
}

/** Character state for the main agent sprite. */
export type CharacterState =
  | "idle"
  | "reading"
  | "typing"
  | "running"
  | "waiting";

/** Map tool name to character state. */
export function toolToState(tool: string): CharacterState {
  const t = tool.toLowerCase();
  if (
    t === "read_file" ||
    t === "list_dir" ||
    t === "glob" ||
    t === "rg" ||
    t === "semantic_search" ||
    t === "web_search" ||
    t === "web_fetch" ||
    t === "mcp_" ||
    t.startsWith("mcp_")
  ) {
    return "reading";
  }
  if (
    t === "write_file" ||
    t === "edit_file" ||
    t === "apply_patch" ||
    t === "edit_notebook" ||
    t === "todowrite"
  ) {
    return "typing";
  }
  if (t === "exec" || t === "run_terminal_cmd" || t === "shell") {
    return "running";
  }
  if (t === "askquestion") return "waiting";
  return "reading";
}
