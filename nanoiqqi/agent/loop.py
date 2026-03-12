"""Agent loop: the core processing engine."""

from __future__ import annotations

import asyncio
import json
import re
from contextlib import AsyncExitStack
from pathlib import Path
from typing import TYPE_CHECKING, Awaitable, Callable

from loguru import logger

from nanoiqqi.agent.activity_events import (
    ToolEndEvent,
    ToolStartEvent,
    TurnEndEvent,
    WaitingInputEvent,
)
from nanoiqqi.agent.activity_sink import ActivitySink, NoOpActivitySink
from nanoiqqi.agent.context import ContextBuilder
from nanoiqqi.agent.memory import MemoryStore
from nanoiqqi.agent.compaction import CompactionSafeguard
from nanoiqqi.agent.subagent import SubagentManager
from nanoiqqi.agent.tools.cron import CronTool
from nanoiqqi.agent.tools.filesystem import EditFileTool, ListDirTool, ReadFileTool, WriteFileTool
from nanoiqqi.agent.tools.message import MessageTool
from nanoiqqi.agent.tools.session_mgmt import DumpSessionTool
from nanoiqqi.agent.tools.registry import ToolRegistry
from nanoiqqi.agent.tools.shell import ExecTool
from nanoiqqi.agent.tools.spawn import SpawnTool
from nanoiqqi.agent.tools.web import WebFetchTool, WebSearchTool
from nanoiqqi.agent.tools.image_gen import GenerateImageTool
from nanoiqqi.agent.tools.leads_mx import LeadsMx
from nanoiqqi.bus.events import InboundMessage, OutboundMessage
from nanoiqqi.bus.queue import MessageBus
from nanoiqqi.providers.base import LLMProvider
from nanoiqqi.session.manager import Session, SessionManager

if TYPE_CHECKING:
    from nanoiqqi.config.schema import ExecToolConfig
    from nanoiqqi.cron.service import CronService


def register_shared_tools(
    registry: ToolRegistry,
    workspace: Path,
    exec_config: "ExecToolConfig",
    brave_api_key: str | None,
    leads_mx_token: str | None,
    image_gen_api_key: str | None,
    image_gen_model: str | None,
    restrict_to_workspace: bool,
) -> None:
    """
    Register tools shared between main agent and subagents.
    Single source of truth: add new user-facing tools here so both get them.
    MCP tools are registered only on the main agent and are not passed to subagents.
    """
    allowed_dir = workspace if restrict_to_workspace else None
    for cls in (ReadFileTool, WriteFileTool, EditFileTool, ListDirTool):
        registry.register(cls(workspace=workspace, allowed_dir=allowed_dir))
    registry.register(ExecTool(
        working_dir=str(workspace),
        timeout=exec_config.timeout,
        restrict_to_workspace=restrict_to_workspace,
    ))
    registry.register(WebSearchTool(api_key=brave_api_key))
    registry.register(WebFetchTool())
    registry.register(
        GenerateImageTool(
            api_key=image_gen_api_key,
            default_model=image_gen_model or "black-forest-labs/flux-2-pro",
            workspace=workspace,
        )
    )
    if leads_mx_token:
        registry.register(LeadsMx(token=leads_mx_token, workspace=workspace))


class SessionCleared(Exception):
    """Signal that the session has been cleared by a tool."""
    pass


class AgentLoop:
    """
    The agent loop is the core processing engine.

    It:
    1. Receives messages from the bus
    2. Builds context with history, memory, skills
    3. Calls the LLM
    4. Executes tool calls
    5. Sends responses back
    """

    def __init__(
        self,
        bus: MessageBus,
        provider: LLMProvider,
        workspace: Path,
        model: str | None = None,
        tool_calling_model: str | None = None,
        max_iterations: int = 20,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        memory_window: int = 50,
        brave_api_key: str | None = None,
        exec_config: ExecToolConfig | None = None,
        cron_service: CronService | None = None,
        restrict_to_workspace: bool = False,
        session_manager: SessionManager | None = None,
        mcp_servers: dict | None = None,
        image_gen_api_key: str | None = None,
        image_gen_model: str | None = None,
        subagent_provider: LLMProvider | None = None,
        subagent_model: str | None = None,
        leads_mx_token: str | None = None,
        activity_sink: ActivitySink | None = None,
        always_skills: list[str] | None = None,
    ):
        from nanoiqqi.config.schema import ExecToolConfig
        self.bus = bus
        self._activity_sink: ActivitySink = activity_sink or NoOpActivitySink()
        self.provider = provider
        self.workspace = workspace
        self.model = model or provider.get_default_model()
        self._tool_calling_model = (tool_calling_model or "").strip() or None
        self.max_iterations = max_iterations
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.memory_window = memory_window
        self.brave_api_key = brave_api_key
        self.exec_config = exec_config or ExecToolConfig()
        self.cron_service = cron_service
        self.restrict_to_workspace = restrict_to_workspace
        self._image_gen_api_key = image_gen_api_key
        self._image_gen_model = image_gen_model
        self._leads_mx_token = (leads_mx_token or "").strip() or None

        self.context = ContextBuilder(
            workspace,
            get_enabled_tool_names=lambda: set(self.tools.tool_names),
            config_always_skills=always_skills or [],
        )
        self.sessions = session_manager or SessionManager(workspace)
        self.tools = ToolRegistry()
        self.safeguard = CompactionSafeguard(provider, summarizer_model="google/gemini-2.5-flash")
        subagent_model_resolved = (subagent_model or "").strip() or self.model

        def subagent_tool_registry_factory() -> ToolRegistry:
            reg = ToolRegistry()
            register_shared_tools(
                reg,
                workspace=self.workspace,
                exec_config=self.exec_config,
                brave_api_key=brave_api_key,
                leads_mx_token=self._leads_mx_token,
                image_gen_api_key=self._image_gen_api_key,
                image_gen_model=self._image_gen_model,
                restrict_to_workspace=restrict_to_workspace,
            )
            return reg

        self.subagents = SubagentManager(
            provider=subagent_provider or provider,
            workspace=workspace,
            bus=bus,
            model=subagent_model_resolved,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            brave_api_key=brave_api_key,
            exec_config=self.exec_config,
            restrict_to_workspace=restrict_to_workspace,
            activity_sink=self._activity_sink,
            subagent_tool_registry_factory=subagent_tool_registry_factory,
        )

        self._running = False
        self._mcp_servers = mcp_servers or {}
        self._mcp_stack: AsyncExitStack | None = None
        self._mcp_connected = False
        self._mcp_connecting = False
        self._consolidating: set[str] = set()  # Session keys with consolidation in progress
        self._register_default_tools()

    def _register_default_tools(self) -> None:
        """Register the default set of tools: shared tools first, then main-only."""
        register_shared_tools(
            self.tools,
            workspace=self.workspace,
            exec_config=self.exec_config,
            brave_api_key=self.brave_api_key,
            leads_mx_token=self._leads_mx_token,
            image_gen_api_key=self._image_gen_api_key,
            image_gen_model=self._image_gen_model,
            restrict_to_workspace=self.restrict_to_workspace,
        )
        self.tools.register(MessageTool(send_callback=self.bus.publish_outbound, workspace=self.workspace))
        self.tools.register(SpawnTool(manager=self.subagents))
        self.tools.register(DumpSessionTool(session_manager=self.sessions, workspace=self.workspace))
        if self.cron_service:
            self.tools.register(CronTool(self.cron_service))

    async def _connect_mcp(self) -> None:
        """Connect to configured MCP servers (one-time, lazy)."""
        if self._mcp_connected or self._mcp_connecting or not self._mcp_servers:
            return
        self._mcp_connecting = True
        from nanoiqqi.agent.tools.mcp import connect_mcp_servers
        try:
            self._mcp_stack = AsyncExitStack()
            await self._mcp_stack.__aenter__()
            await connect_mcp_servers(self._mcp_servers, self.tools, self._mcp_stack)
            self._mcp_connected = True
        except Exception as e:
            logger.error("Failed to connect MCP servers (will retry next message): {}", e)
            if self._mcp_stack:
                try:
                    await self._mcp_stack.aclose()
                except Exception:
                    pass
                self._mcp_stack = None
        finally:
            self._mcp_connecting = False

    def _set_tool_context(self, channel: str, chat_id: str, message_id: str | None = None) -> None:
        """Update context for all tools that need routing info."""
        if message_tool := self.tools.get("message"):
            if isinstance(message_tool, MessageTool):
                message_tool.set_context(channel, chat_id, message_id)

        if spawn_tool := self.tools.get("spawn"):
            if isinstance(spawn_tool, SpawnTool):
                spawn_tool.set_context(channel, chat_id)

        if cron_tool := self.tools.get("cron"):
            if isinstance(cron_tool, CronTool):
                cron_tool.set_context(channel, chat_id)

        if dump_tool := self.tools.get("new_session"):
            if isinstance(dump_tool, DumpSessionTool):
                dump_tool.set_context(channel, chat_id)

    @staticmethod
    def _estimate_messages_tokens(messages: list[dict]) -> int:
        """Estimate token count for messages (heuristic char//4). Handles content as str or list of parts."""
        total = 0
        for m in messages:
            content = m.get("content", "")
            if isinstance(content, str):
                total += len(content) // 4
            elif isinstance(content, list):
                for part in content:
                    if isinstance(part, dict) and part.get("type") == "text":
                        total += len(part.get("text", "")) // 4
                    elif isinstance(part, str):
                        total += len(part) // 4
            if "tool_calls" in m:
                total += len(json.dumps(m["tool_calls"], ensure_ascii=False)) // 4
        return total

    @staticmethod
    def _strip_think(text: str | None) -> str | None:
        """Remove <think>…</think> blocks that some models embed in content."""
        if not text:
            return None
        return re.sub(r"<think>[\s\S]*?</think>", "", text).strip() or None

    @staticmethod
    def _extract_media_from_content(content: str | None, workspace: Path) -> tuple[str, list[str]]:
        """
        Extract local file paths from markdown image syntax in content and return
        (sanitized_content, media_paths). Only paths under workspace or ~/.nanoiqqi
        that exist and are files are included. Sanitized content has those
        markdown image segments removed so the user does not see raw paths.
        """
        if not content or not content.strip():
            return (content or "", [])
        allowed_roots = [
            workspace.resolve(),
            (Path.home() / ".nanoiqqi").resolve(),
        ]
        # Match ![alt](path) or ![](path)
        pattern = re.compile(r"!\[[^\]]*\]\s*\(\s*([^)]+)\s*\)")
        media_paths: list[str] = []
        seen: set[str] = set()

        def repl(match: re.Match[str]) -> str:
            raw = match.group(1).strip()
            if not raw or raw.startswith("http://") or raw.startswith("https://"):
                return match.group(0)
            try:
                p = Path(raw).expanduser()
                if not p.is_absolute():
                    p = (workspace / raw).resolve()
                else:
                    p = p.resolve()
                if not p.is_file():
                    return match.group(0)
                try:
                    in_allowed = any(
                        p == root or str(p).startswith(str(root) + "/")
                        for root in allowed_roots
                    )
                except ValueError:
                    in_allowed = False
                if in_allowed:
                    path_str = str(p)
                    if path_str not in seen:
                        seen.add(path_str)
                        media_paths.append(path_str)
                    return ""
            except (OSError, RuntimeError):
                pass
            return match.group(0)

        sanitized = pattern.sub(repl, content)
        # Collapse multiple newlines/spaces left after stripping image markdown
        sanitized = re.sub(r"\n{3,}", "\n\n", sanitized).strip()
        return (sanitized, media_paths)

    @staticmethod
    def _tool_hint(tool_calls: list) -> str:
        """Format tool calls as concise hint, e.g. 'web_search("query")'."""
        def _fmt(tc):
            val = next(iter(tc.arguments.values()), None) if tc.arguments else None
            if not isinstance(val, str):
                return tc.name
            return f'{tc.name}("{val[:40]}…")' if len(val) > 40 else f'{tc.name}("{val}")'
        return ", ".join(_fmt(tc) for tc in tool_calls)

    async def _run_agent_loop(
        self,
        initial_messages: list[dict],
        on_progress: Callable[[str], Awaitable[None]] | None = None,
        model_override: str | None = None,
        session_id: str = "",
    ) -> tuple[str | None, list[str]]:
        """Run the agent iteration loop. Returns (final_content, tools_used)."""
        # Apply Compaction Safeguard
        messages = await self.safeguard.process(initial_messages)
        
        iteration = 0
        final_content = None
        tools_used: list[str] = []
        effective_model = model_override or self._tool_calling_model or self.model

        while iteration < self.max_iterations:
            iteration += 1

            force_model = (
                self._tool_calling_model is not None
                and effective_model == self._tool_calling_model
            )
            response = await self.provider.chat(
                messages=messages,
                tools=self.tools.get_definitions(),
                model=effective_model,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                force_model=force_model,
            )

            if response.has_tool_calls:
                if on_progress:
                    clean = self._strip_think(response.content)
                    if clean:
                        await on_progress(clean)
                    await on_progress(self._tool_hint(response.tool_calls))

                tool_call_dicts = [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.name,
                            "arguments": json.dumps(tc.arguments, ensure_ascii=False)
                        }
                    }
                    for tc in response.tool_calls
                ]
                messages = self.context.add_assistant_message(
                    messages, response.content, tool_call_dicts,
                    reasoning_content=response.reasoning_content,
                )

                for tool_call in response.tool_calls:
                    tools_used.append(tool_call.name)
                    args_str = json.dumps(tool_call.arguments, ensure_ascii=False)
                    logger.info("Tool call: {}({})", tool_call.name, args_str[:200])
                    await self._activity_sink.emit(
                        ToolStartEvent(tool=tool_call.name, session_id=session_id)
                    )
                    result = await self.tools.execute(tool_call.name, tool_call.arguments)
                    await self._activity_sink.emit(
                        ToolEndEvent(tool=tool_call.name, session_id=session_id)
                    )
                    if "[CLEAR_SESSION_STATE_NOW]" in result:
                        raise SessionCleared(result.replace("[CLEAR_SESSION_STATE_NOW]", "").strip())

                    messages = self.context.add_tool_result(
                        messages, tool_call.id, tool_call.name, result
                    )

                # Mid-turn compression: avoid context overflow after many tool calls
                estimated = self._estimate_messages_tokens(messages)
                if (
                    estimated >= CompactionSafeguard.TRIGGER_TOKENS
                    or iteration % 5 == 0
                ):
                    messages = await self.safeguard.process(messages)
            else:
                final_content = self._strip_think(response.content)
                break

        return final_content, tools_used

    async def run(self) -> None:
        """Run the agent loop, processing messages from the bus."""
        self._running = True
        await self._connect_mcp()
        logger.info("Agent loop started")

        while self._running:
            try:
                msg = await asyncio.wait_for(
                    self.bus.consume_inbound(),
                    timeout=1.0
                )
                try:
                    response = await self._process_message(msg)
                    if response is not None:
                        await self.bus.publish_outbound(response)
                    elif msg.channel == "cli":
                        await self.bus.publish_outbound(OutboundMessage(
                            channel=msg.channel, chat_id=msg.chat_id, content="", metadata=msg.metadata or {},
                        ))
                except Exception as e:
                    logger.error("Error processing message: {}", e)
                    await self.bus.publish_outbound(OutboundMessage(
                        channel=msg.channel,
                        chat_id=msg.chat_id,
                        content=f"Sorry, I encountered an error: {str(e)}"
                    ))
            except asyncio.TimeoutError:
                continue

    async def close_mcp(self) -> None:
        """Close MCP connections."""
        if self._mcp_stack:
            try:
                await self._mcp_stack.aclose()
            except (RuntimeError, BaseExceptionGroup):
                pass  # MCP SDK cancel scope cleanup is noisy but harmless
            self._mcp_stack = None

    def stop(self) -> None:
        """Stop the agent loop."""
        self._running = False
        logger.info("Agent loop stopping")

    async def _process_message(
        self,
        msg: InboundMessage,
        session_key: str | None = None,
        on_progress: Callable[[str], Awaitable[None]] | None = None,
        model_override: str | None = None,
    ) -> OutboundMessage | None:
        """Process a single inbound message and return the response."""
        # System messages: parse origin from chat_id ("channel:chat_id")
        if msg.channel == "system":
            channel, chat_id = (msg.chat_id.split(":", 1) if ":" in msg.chat_id
                                else ("cli", msg.chat_id))
            logger.info("Processing system message from {}", msg.sender_id)
            key = f"{channel}:{chat_id}"
            session = self.sessions.get_or_create(key)
            self._set_tool_context(channel, chat_id, msg.metadata.get("message_id"))
            messages = self.context.build_messages(
                history=session.get_history(max_messages=self.memory_window),
                current_message=msg.content, channel=channel, chat_id=chat_id,
            )
            final_content, _ = await self._run_agent_loop(
                messages, model_override=model_override, session_id=key
            )
            session.add_message("user", f"[System: {msg.sender_id}] {msg.content}")
            session.add_message("assistant", final_content or "Background task completed.")
            self.sessions.save(session)
            content_out, media_paths = self._extract_media_from_content(final_content, self.workspace)
            return OutboundMessage(
                channel=channel,
                chat_id=chat_id,
                content=content_out or "Background task completed.",
                media=media_paths,
            )

        preview = msg.content[:80] + "..." if len(msg.content) > 80 else msg.content
        logger.info("Processing message from {}:{}: {}", msg.channel, msg.sender_id, preview)

        key = session_key or msg.session_key
        session = self.sessions.get_or_create(key)

        # Slash commands
        cmd = msg.content.strip().lower()
        if cmd == "/new":
            messages_to_archive = session.messages.copy()
            session.clear()
            self.sessions.save(session)
            self.sessions.invalidate(session.key)

            async def _consolidate_and_cleanup():
                temp = Session(key=session.key)
                temp.messages = messages_to_archive
                await self._consolidate_memory(temp, archive_all=True)

            asyncio.create_task(_consolidate_and_cleanup())
            return OutboundMessage(channel=msg.channel, chat_id=msg.chat_id,
                                  content="New session started. Memory consolidation in progress.")
        if cmd == "/help":
            return OutboundMessage(channel=msg.channel, chat_id=msg.chat_id,
                                  content="⚡ iqqibot commands:\n/new — Start a new conversation\n/help — Show available commands")

        if len(session.messages) > self.memory_window and session.key not in self._consolidating:
            self._consolidating.add(session.key)

            async def _consolidate_and_unlock():
                try:
                    await self._consolidate_memory(session)
                finally:
                    self._consolidating.discard(session.key)

            asyncio.create_task(_consolidate_and_unlock())

        self._set_tool_context(msg.channel, msg.chat_id, msg.metadata.get("message_id"))
        if message_tool := self.tools.get("message"):
            if isinstance(message_tool, MessageTool):
                message_tool.start_turn()

        initial_messages = self.context.build_messages(
            history=session.get_history(max_messages=self.memory_window),
            current_message=msg.content,
            media=msg.media if msg.media else None,
            channel=msg.channel, chat_id=msg.chat_id,
        )

        async def _bus_progress(content: str) -> None:
            meta = dict(msg.metadata or {})
            meta["_progress"] = True
            await self.bus.publish_outbound(OutboundMessage(
                channel=msg.channel, chat_id=msg.chat_id, content=content, metadata=meta,
            ))

        try:
            final_content, tools_used = await self._run_agent_loop(
                initial_messages,
                on_progress=on_progress or _bus_progress,
                model_override=model_override,
                session_id=key,
            )
        except SessionCleared as e:
            session.clear()
            self.safeguard._safeguard_active = False
            self.sessions.save(session)
            final_content = str(e)
            tools_used = ["new_session"]

        if final_content is None:
            final_content = "I've completed processing but have no response to give."

        preview = final_content[:120] + "..." if len(final_content) > 120 else final_content
        logger.info("Response to {}:{}: {}", msg.channel, msg.sender_id, preview)

        session.add_message("user", msg.content)
        session.add_message("assistant", final_content,
                            tools_used=tools_used if tools_used else None)
        self.sessions.save(session)

        if message_tool := self.tools.get("message"):
            if isinstance(message_tool, MessageTool) and message_tool._sent_in_turn:
                await self._activity_sink.emit(TurnEndEvent(session_id=key))
                await self._activity_sink.emit(WaitingInputEvent(session_id=key))
                return None

        await self._activity_sink.emit(TurnEndEvent(session_id=key))
        await self._activity_sink.emit(WaitingInputEvent(session_id=key))
        content_out, media_paths = self._extract_media_from_content(final_content, self.workspace)
        return OutboundMessage(
            channel=msg.channel,
            chat_id=msg.chat_id,
            content=content_out,
            media=media_paths,
            metadata=msg.metadata or {},
        )

    async def _consolidate_memory(self, session, archive_all: bool = False) -> None:
        """Delegate to MemoryStore.consolidate()."""
        await MemoryStore(self.workspace).consolidate(
            session, self.provider, self.model,
            archive_all=archive_all, memory_window=self.memory_window,
        )

    async def process_direct(
        self,
        content: str,
        session_key: str = "cli:direct",
        channel: str = "cli",
        chat_id: str = "direct",
        on_progress: Callable[[str], Awaitable[None]] | None = None,
        model: str | None = None,
    ) -> str:
        """Process a message directly (for CLI or cron usage).

        Args:
            model: Optional model override (e.g. cheap model for heartbeat).
        """
        await self._connect_mcp()
        msg = InboundMessage(channel=channel, sender_id="user", chat_id=chat_id, content=content)
        response = await self._process_message(
            msg, session_key=session_key, on_progress=on_progress, model_override=model,
        )
        return response.content if response else ""
