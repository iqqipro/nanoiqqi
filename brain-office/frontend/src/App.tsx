import { useEffect, useMemo, useState, type KeyboardEvent } from "react";

import type { ChatMessage } from "./types";
import { OfficeEditor } from "./components/OfficeEditor";
import { OfficeGrid, StatusLabel } from "./components/OfficeGrid";
import { buildOfficeLayout, type OfficeLayout } from "./components/officeLayout";
import { useActivitySocket } from "./useActivitySocket";
import "./App.css";

const GRID_PRESETS = [
  { id: "studio", label: "Studio 24 x 18", cols: 24, rows: 18, tileSize: 28 },
  { id: "ops", label: "Ops Floor 32 x 24", cols: 32, rows: 24, tileSize: 24 },
  { id: "hq", label: "HQ 48 x 32", cols: 48, rows: 32, tileSize: 18 },
] as const;

const THEME_STORAGE_KEY = "iqqi-baby-brain-office-theme";

type Theme = "dark" | "light";

function getInitialTheme(): Theme {
  const stored = window.localStorage.getItem(THEME_STORAGE_KEY);
  if (stored === "dark" || stored === "light") {
    return stored;
  }
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

function mediaType(url: string) {
  const clean = url.split("?")[0].toLowerCase();
  if (/\.(mp4|webm|mov|m4v|ogg)$/i.test(clean)) {
    return "video";
  }
  if (/\.(png|jpe?g|gif|webp|svg)$/i.test(clean) || clean.startsWith("data:image/")) {
    return "image";
  }
  return "file";
}

function MessageMedia({ message }: { message: ChatMessage }) {
  if (!message.media?.length) {
    return null;
  }

  return (
    <div className="mt-3 grid gap-3">
      {message.media.map((item, index) => {
        const kind = mediaType(item);
        if (kind === "video") {
          return (
            <video
              key={`${message.id}-${index}`}
              className="chat-media"
              controls
              preload="metadata"
              src={item}
            />
          );
        }
        if (kind === "image") {
          return (
            <img
              key={`${message.id}-${index}`}
              className="chat-media"
              src={item}
              alt={`Media ${index + 1}`}
            />
          );
        }
        return (
          <a
            key={`${message.id}-${index}`}
            className="chat-media-link"
            href={item}
            target="_blank"
            rel="noreferrer"
          >
            Open attachment {index + 1}
          </a>
        );
      })}
    </div>
  );
}

function App() {
  const [theme, setTheme] = useState<Theme>(() => getInitialTheme());
  const [presetId, setPresetId] = useState<(typeof GRID_PRESETS)[number]["id"]>("ops");
  const [layout, setLayout] = useState<OfficeLayout>(() => buildOfficeLayout(32, 24));
  const [commandInput, setCommandInput] = useState("");
  const [subagentTask, setSubagentTask] = useState("");
  const [subagentName, setSubagentName] = useState("");
  const [showEditor, setShowEditor] = useState(false);
  const [uiError, setUiError] = useState<string | null>(null);
  const [isSending, setIsSending] = useState(false);
  const [isSpawning, setIsSpawning] = useState(false);
  const {
    characterState,
    lastTool,
    connectionStatus,
    chatMessages,
    subagents,
    sendChatCommand,
    spawnSubagent,
  } = useActivitySocket();

  const preset = useMemo(
    () => GRID_PRESETS.find((entry) => entry.id === presetId) ?? GRID_PRESETS[1],
    [presetId]
  );

  useEffect(() => {
    setLayout(buildOfficeLayout(preset.cols, preset.rows));
  }, [preset.cols, preset.rows]);

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    window.localStorage.setItem(THEME_STORAGE_KEY, theme);
  }, [theme]);

  async function handleSendCommand() {
    try {
      setIsSending(true);
      setUiError(null);
      await sendChatCommand(commandInput);
      setCommandInput("");
    } catch (error) {
      setUiError(error instanceof Error ? error.message : "Could not send command.");
    } finally {
      setIsSending(false);
    }
  }

  async function handleSpawnSubagent() {
    try {
      setIsSpawning(true);
      setUiError(null);
      await spawnSubagent(subagentTask, subagentName);
      setSubagentTask("");
      setSubagentName("");
    } catch (error) {
      setUiError(error instanceof Error ? error.message : "Could not spawn subagent.");
    } finally {
      setIsSpawning(false);
    }
  }

  function handleChatKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      void handleSendCommand();
    }
  }

  const cardClass =
    theme === "dark"
      ? "rounded-[28px] border border-white/10 bg-zinc-950/90 text-zinc-100 shadow-2xl shadow-black/25"
      : "rounded-[28px] border border-black/10 bg-white/95 text-zinc-950 shadow-xl shadow-black/10";

  const softCardClass =
    theme === "dark"
      ? "rounded-[24px] border border-white/10 bg-zinc-950/85 text-zinc-100 shadow-xl shadow-black/20"
      : "rounded-[24px] border border-black/10 bg-white text-zinc-950 shadow-lg shadow-black/8";

  const inputClass =
    theme === "dark"
      ? "w-full rounded-2xl border border-white/10 bg-zinc-900 px-4 py-3 text-sm text-white outline-none transition focus:border-lime-400/60"
      : "w-full rounded-2xl border border-black/10 bg-zinc-50 px-4 py-3 text-sm text-zinc-950 outline-none transition focus:border-lime-600/60";

  const transcriptEmptyClass =
    theme === "dark"
      ? "rounded-2xl border border-dashed border-white/10 px-4 py-5 text-sm text-zinc-400"
      : "rounded-2xl border border-dashed border-black/10 px-4 py-5 text-sm text-zinc-500";

  return (
    <div className="brain-office" data-theme={theme}>
      <div className="mx-auto flex min-h-screen w-full max-w-[1920px] flex-col gap-4 px-3 py-4 lg:px-4">
        <header className={`${cardClass} p-5 backdrop-blur-xl`}>
          <div className="flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between">
            <div className="flex items-start gap-4 text-left">
              <img
                src="/iqqifavicon.svg"
                alt="IQQI logo"
                className="h-14 w-14 rounded-2xl border border-current/10 object-contain p-2"
              />
              <div className="space-y-2">
                <div className="inline-flex items-center rounded-full border border-lime-400/20 bg-lime-400/10 px-3 py-1 text-xs font-semibold uppercase tracking-[0.24em] text-lime-500">
                  IQQI Control Center
                </div>
                <div>
                  <h1 className="text-4xl font-black tracking-tight sm:text-5xl">
                    IQQI Baby Brain Office
                  </h1>
                  <p className={`mt-2 max-w-3xl text-sm sm:text-base ${theme === "dark" ? "text-zinc-300" : "text-zinc-600"}`}>
                    Chat natural con el agente, media inline, subagentes visuales y oficina dinámica con Brain Baby.
                  </p>
                </div>
              </div>
            </div>

            <div className={`flex flex-wrap items-center gap-3 rounded-2xl border p-3 ${theme === "dark" ? "border-white/10 bg-zinc-900" : "border-black/10 bg-zinc-50"}`}>
              <button
                type="button"
                className={`rounded-xl px-4 py-2 text-sm font-semibold transition ${
                  theme === "dark"
                    ? "bg-white text-black hover:bg-zinc-200"
                    : "bg-black text-white hover:bg-zinc-800"
                }`}
                onClick={() => setTheme((current) => (current === "dark" ? "light" : "dark"))}
              >
                {theme === "dark" ? "Light mode" : "Dark mode"}
              </button>

              <label className={`text-xs font-semibold uppercase tracking-[0.2em] ${theme === "dark" ? "text-zinc-300" : "text-zinc-500"}`} htmlFor="office-size">
                Office size
              </label>
              <select
                id="office-size"
                className={inputClass}
                value={presetId}
                onChange={(event) =>
                  setPresetId(event.target.value as (typeof GRID_PRESETS)[number]["id"])
                }
              >
                {GRID_PRESETS.map((entry) => (
                  <option key={entry.id} value={entry.id}>
                    {entry.label}
                  </option>
                ))}
              </select>
            </div>
          </div>
        </header>

        <main className="grid items-start gap-4 xl:grid-cols-[minmax(0,1.9fr)_380px]">
          <section className="space-y-3">
            <div className={softCardClass}>
              <div className="border-b border-current/10 px-4 py-3">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div>
                    <h2 className="text-lg font-bold">Office Live View</h2>
                    <p className={`text-sm ${theme === "dark" ? "text-zinc-400" : "text-zinc-600"}`}>
                      El agente se mueve por la oficina según su tarea actual.
                    </p>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    <span className={`rounded-full px-3 py-1 text-xs font-semibold ${theme === "dark" ? "bg-white/8 text-zinc-200" : "bg-black/5 text-zinc-700"}`}>
                      {`${preset.cols} x ${preset.rows} tiles`}
                    </span>
                    <span className="rounded-full bg-lime-400/12 px-3 py-1 text-xs font-semibold text-lime-600">
                      {`Subagents ${subagents.filter((entry) => entry.status === "running").length}`}
                    </span>
                  </div>
                </div>
              </div>
              <div className="p-3">
                <OfficeGrid
                  characterState={characterState}
                  lastTool={lastTool}
                  layout={layout}
                  subagents={subagents}
                  tileSize={preset.tileSize}
                />
                <StatusLabel
                  characterState={characterState}
                  lastTool={lastTool}
                  connectionStatus={connectionStatus}
                />
              </div>
            </div>
          </section>

          <aside className="space-y-3">
            <div className={`${softCardClass} p-3`}>
              <div className="mb-3 flex items-center justify-between gap-3">
                <div>
                  <h2 className="text-lg font-bold">Natural Agent Chat</h2>
                  <p className={`text-sm ${theme === "dark" ? "text-zinc-400" : "text-zinc-600"}`}>
                    Conversa con el agente y sigue las respuestas en tiempo real dentro del mismo bloque.
                  </p>
                </div>
                <span className={`rounded-full px-3 py-1 text-xs font-semibold uppercase tracking-[0.18em] ${theme === "dark" ? "bg-white/8 text-zinc-200" : "bg-black/5 text-zinc-700"}`}>
                  {connectionStatus}
                </span>
              </div>
              <div className="chat-scroll mb-3 flex max-h-[440px] flex-col gap-2 overflow-auto pr-1">
                {chatMessages.length === 0 ? (
                  <div className={transcriptEmptyClass}>
                    Aún no hay mensajes. Empieza una conversación o pide a un subagente que investigue algo.
                  </div>
                ) : (
                  chatMessages.map((message) => (
                    <div
                      key={message.id}
                      className={`rounded-2xl border px-4 py-3 text-sm ${
                        message.role === "user"
                          ? theme === "dark"
                            ? "border-lime-400/20 bg-lime-400/10 text-zinc-100"
                            : "border-lime-500/20 bg-lime-500/10 text-zinc-900"
                          : message.role === "progress"
                            ? theme === "dark"
                              ? "border-white/10 bg-white/[0.04] text-zinc-100"
                              : "border-black/10 bg-black/5 text-zinc-900"
                            : message.role === "system"
                              ? theme === "dark"
                                ? "border-zinc-700 bg-zinc-900 text-zinc-100"
                                : "border-zinc-200 bg-zinc-100 text-zinc-900"
                              : theme === "dark"
                                ? "border-white/10 bg-zinc-900 text-zinc-100"
                                : "border-black/10 bg-zinc-50 text-zinc-900"
                      }`}
                    >
                      <div className={`mb-2 flex items-center justify-between gap-3 text-[11px] uppercase tracking-[0.18em] ${theme === "dark" ? "text-zinc-400" : "text-zinc-500"}`}>
                        <span>{message.name || message.role}</span>
                        <span>{new Date(message.ts).toLocaleTimeString()}</span>
                      </div>
                      {message.content ? <p className="whitespace-pre-wrap">{message.content}</p> : null}
                      <MessageMedia message={message} />
                    </div>
                  ))
                )}
              </div>
              <div className="space-y-2 border-t border-current/10 pt-3">
                <textarea
                  className={`${inputClass} min-h-[104px]`}
                  placeholder="Ejemplo: revisa el frontend, explícame el error y si puedes genera una imagen del resultado."
                  value={commandInput}
                  onChange={(event) => setCommandInput(event.target.value)}
                  onKeyDown={handleChatKeyDown}
                />
                <button
                  type="button"
                  className={`inline-flex w-full items-center justify-center rounded-2xl px-4 py-2.5 text-sm font-bold transition disabled:cursor-not-allowed disabled:opacity-50 ${
                    theme === "dark"
                      ? "bg-lime-400 text-black hover:bg-lime-300"
                      : "bg-black text-white hover:bg-zinc-800"
                  }`}
                  onClick={() => void handleSendCommand()}
                  disabled={isSending || !commandInput.trim()}
                >
                  {isSending ? "Sending..." : "Send message"}
                </button>
              </div>
              {uiError ? <p className="mt-3 text-sm text-rose-500">{uiError}</p> : null}
            </div>

            <div className={`${softCardClass} p-3`}>
              <div className="mb-3 flex items-center justify-between gap-3">
                <div>
                  <h2 className="text-lg font-bold">Graphic Subagents</h2>
                  <p className={`text-sm ${theme === "dark" ? "text-zinc-400" : "text-zinc-600"}`}>
                    Crea subagentes y revisa su estado visual sin romper el flujo del chat.
                  </p>
                </div>
                <button
                  type="button"
                  className={`rounded-xl px-3 py-2 text-xs font-semibold uppercase tracking-[0.14em] ${
                    theme === "dark" ? "bg-white/8 text-zinc-200" : "bg-black/5 text-zinc-700"
                  }`}
                  onClick={() => setShowEditor((current) => !current)}
                >
                  {showEditor ? "Hide editor" : "Show editor"}
                </button>
              </div>
              <div className="mb-3 space-y-2">
                <input
                  className={inputClass}
                  placeholder="Nombre, por ejemplo: Atlas"
                  value={subagentName}
                  onChange={(event) => setSubagentName(event.target.value)}
                />
                <textarea
                  className={`${inputClass} min-h-[84px]`}
                  placeholder="Tarea del subagente, por ejemplo: analiza el backend y reporta errores."
                  value={subagentTask}
                  onChange={(event) => setSubagentTask(event.target.value)}
                />
                <button
                  type="button"
                  className={`inline-flex w-full items-center justify-center rounded-2xl px-4 py-2.5 text-sm font-bold transition disabled:cursor-not-allowed disabled:opacity-50 ${
                    theme === "dark"
                      ? "bg-zinc-100 text-black hover:bg-zinc-300"
                      : "bg-zinc-900 text-white hover:bg-zinc-700"
                  }`}
                  onClick={() => void handleSpawnSubagent()}
                  disabled={isSpawning || !subagentTask.trim()}
                >
                  {isSpawning ? "Spawning..." : "Create subagent"}
                </button>
              </div>
              <div className="grid gap-2">
                {subagents.length === 0 ? (
                  <div className={transcriptEmptyClass}>Todavía no hay subagentes activos.</div>
                ) : (
                  subagents.map((entry) => (
                    <div
                      key={entry.id}
                      className={`flex items-center justify-between rounded-2xl border px-3 py-2.5 ${
                        theme === "dark" ? "border-white/8 bg-white/[0.03]" : "border-black/8 bg-black/[0.02]"
                      }`}
                    >
                      <div>
                        <p className="text-sm font-semibold">{entry.label}</p>
                        <p className={`text-xs uppercase tracking-[0.18em] ${theme === "dark" ? "text-zinc-500" : "text-zinc-500"}`}>
                          {entry.id}
                        </p>
                      </div>
                      <span
                        className={`rounded-full px-3 py-1 text-xs font-bold ${
                          entry.status === "running"
                            ? "bg-lime-400/12 text-lime-600"
                            : theme === "dark"
                              ? "bg-white/8 text-zinc-200"
                              : "bg-black/5 text-zinc-700"
                        }`}
                      >
                        {entry.status}
                      </span>
                    </div>
                  ))
                )}
              </div>
            </div>
          </aside>
        </main>

        {showEditor ? (
          <section>
            <OfficeEditor
              characterState={characterState}
              lastTool={lastTool}
              tileSize={preset.tileSize}
              layout={layout}
              onChange={setLayout}
              onReset={() => setLayout(buildOfficeLayout(preset.cols, preset.rows))}
            />
          </section>
        ) : null}
      </div>
    </div>
  );
}

export default App;
