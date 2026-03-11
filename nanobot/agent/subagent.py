"""Subagent manager for background task execution."""

import asyncio
import json
import uuid
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable

from loguru import logger

from nanobot.bus.events import InboundMessage

if TYPE_CHECKING:
    from nanobot.agent.activity_sink import ActivitySink
from nanobot.bus.queue import MessageBus
from nanobot.providers.base import LLMProvider
from nanobot.agent.tools.registry import ToolRegistry


# Max estimated tokens before trimming subagent conversation history.
SUBAGENT_MAX_TOKENS = 80_000
# Number of most recent messages to keep when trimming (assistant/tool alternation).
SUBAGENT_TRIM_LAST_K = 6


class SubagentManager:
    """
    Manages background subagent execution.
    
    Subagents are lightweight agent instances that run in the background
    to handle specific tasks. They share the same LLM provider but have
    isolated context and a focused system prompt.
    """

    @staticmethod
    def _estimate_messages_tokens(messages: list[dict[str, Any]]) -> int:
        """Estimate token count (heuristic char//4). Content may be str or list of parts."""
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
    def _trim_messages_if_needed(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """
        If token estimate exceeds SUBAGENT_MAX_TOKENS, keep system, first user,
        last SUBAGENT_TRIM_LAST_K messages, and replace the middle with a summary message.
        """
        if len(messages) <= 2 + SUBAGENT_TRIM_LAST_K:
            return messages
        estimated = SubagentManager._estimate_messages_tokens(messages)
        if estimated <= SUBAGENT_MAX_TOKENS:
            return messages
        # Count tool messages in the middle block (between index 1 and last K)
        middle = messages[2 : -(SUBAGENT_TRIM_LAST_K)] if SUBAGENT_TRIM_LAST_K > 0 else messages[2:]
        n_tool = sum(1 for m in middle if m.get("role") == "tool")
        summary = {
            "role": "system",
            "content": f"Resumen: el subagente ejecutó {n_tool} herramientas; últimos resultados resumidos.",
        }
        return [
            messages[0],
            messages[1],
            summary,
            *messages[-SUBAGENT_TRIM_LAST_K:],
        ]
    
    def __init__(
        self,
        provider: LLMProvider,
        workspace: Path,
        bus: MessageBus,
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        brave_api_key: str | None = None,
        exec_config: "ExecToolConfig | None" = None,
        restrict_to_workspace: bool = False,
        activity_sink: "ActivitySink | None" = None,
        subagent_tool_registry_factory: Callable[[], ToolRegistry] | None = None,
    ):
        from nanobot.agent.activity_sink import NoOpActivitySink
        from nanobot.config.schema import ExecToolConfig
        self.provider = provider
        self.workspace = workspace
        self.bus = bus
        self.model = model or provider.get_default_model()
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.brave_api_key = brave_api_key
        self.exec_config = exec_config or ExecToolConfig()
        self.restrict_to_workspace = restrict_to_workspace
        self._activity_sink = activity_sink or NoOpActivitySink()
        self._subagent_tool_registry_factory = subagent_tool_registry_factory
        self._running_tasks: dict[str, asyncio.Task[None]] = {}
    
    async def spawn(
        self,
        task: str,
        label: str | None = None,
        origin_channel: str = "cli",
        origin_chat_id: str = "direct",
    ) -> str:
        """
        Spawn a subagent to execute a task in the background.
        
        Args:
            task: The task description for the subagent.
            label: Optional human-readable label for the task.
            origin_channel: The channel to announce results to.
            origin_chat_id: The chat ID to announce results to.
        
        Returns:
            Status message indicating the subagent was started.
        """
        task_id = str(uuid.uuid4())[:8]
        display_label = label or task[:30] + ("..." if len(task) > 30 else "")
        
        origin = {
            "channel": origin_channel,
            "chat_id": origin_chat_id,
        }
        
        # Create background task
        bg_task = asyncio.create_task(
            self._run_subagent(task_id, task, display_label, origin)
        )
        self._running_tasks[task_id] = bg_task
        
        # Cleanup when done
        bg_task.add_done_callback(lambda _: self._running_tasks.pop(task_id, None))
        
        logger.info("Spawned subagent [{}]: {}", task_id, display_label)
        return f"Subagent [{display_label}] started (id: {task_id}). I'll notify you when it completes."
    
    async def _run_subagent(
        self,
        task_id: str,
        task: str,
        label: str,
        origin: dict[str, str],
    ) -> None:
        """Execute the subagent task and announce the result."""
        from nanobot.agent.activity_events import SubagentEndEvent, SubagentStartEvent

        parent_session_id = f"{origin['channel']}:{origin['chat_id']}"
        await self._activity_sink.emit(
            SubagentStartEvent(id=task_id, label=label, parent_session_id=parent_session_id)
        )
        logger.info("Subagent [{}] starting task: {}", task_id, label)

        try:
            # Build subagent tools from shared factory (includes LeadsMx, filesystem, web, etc.; no message/spawn)
            if self._subagent_tool_registry_factory:
                tools = self._subagent_tool_registry_factory()
            else:
                tools = ToolRegistry()

            # Build messages with subagent-specific prompt
            system_prompt = self._build_subagent_prompt(task)
            messages: list[dict[str, Any]] = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": task},
            ]
            
            # Run agent loop (limited iterations)
            max_iterations = 15
            iteration = 0
            final_result: str | None = None
            
            while iteration < max_iterations:
                iteration += 1

                messages = self._trim_messages_if_needed(messages)

                response = await self.provider.chat(
                    messages=messages,
                    tools=tools.get_definitions(),
                    model=self.model,
                    temperature=self.temperature,
                    max_tokens=self.max_tokens,
                    routing_profile="subagent",
                )
                
                if response.has_tool_calls:
                    # Add assistant message with tool calls
                    tool_call_dicts = [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {
                                "name": tc.name,
                                "arguments": json.dumps(tc.arguments, ensure_ascii=False),
                            },
                        }
                        for tc in response.tool_calls
                    ]
                    messages.append({
                        "role": "assistant",
                        "content": response.content or "",
                        "tool_calls": tool_call_dicts,
                    })
                    
                    # Execute tools
                    for tool_call in response.tool_calls:
                        args_str = json.dumps(tool_call.arguments, ensure_ascii=False)
                        logger.debug("Subagent [{}] executing: {} with arguments: {}", task_id, tool_call.name, args_str)
                        result = await tools.execute(tool_call.name, tool_call.arguments)
                        messages.append({
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "name": tool_call.name,
                            "content": result,
                        })
                else:
                    final_result = response.content
                    break
            
            if final_result is None:
                final_result = "Task completed but no final response was generated."

            logger.info("Subagent [{}] completed successfully", task_id)
            await self._announce_result(task_id, label, task, final_result, origin, "ok")

        except Exception as e:
            error_msg = f"Error: {str(e)}"
            logger.error("Subagent [{}] failed: {}", task_id, e)
            await self._announce_result(task_id, label, task, error_msg, origin, "error")
        finally:
            await self._activity_sink.emit(SubagentEndEvent(id=task_id, label=label))
    
    async def _announce_result(
        self,
        task_id: str,
        label: str,
        task: str,
        result: str,
        origin: dict[str, str],
        status: str,
    ) -> None:
        """Announce the subagent result to the main agent via the message bus."""
        status_text = "completed successfully" if status == "ok" else "failed"
        
        announce_content = f"""[Subagent '{label}' {status_text}]

Task: {task}

Result:
{result}

Summarize this naturally for the user. Keep it brief (1-2 sentences). Do not mention technical details like "subagent" or task IDs."""
        
        # Inject as system message to trigger main agent
        msg = InboundMessage(
            channel="system",
            sender_id="subagent",
            chat_id=f"{origin['channel']}:{origin['chat_id']}",
            content=announce_content,
        )
        
        await self.bus.publish_inbound(msg)
        logger.debug("Subagent [{}] announced result to {}:{}", task_id, origin['channel'], origin['chat_id'])
    
    def _build_subagent_prompt(self, task: str) -> str:
        """Build a focused system prompt for the subagent."""
        from datetime import datetime
        import time as _time
        now = datetime.now().strftime("%Y-%m-%d %H:%M (%A)")
        tz = _time.strftime("%Z") or "UTC"

        return f"""# Subagent

## Current Time
{now} ({tz})

You are a subagent spawned by the main agent to complete a specific task.

## Rules
1. Stay focused - complete only the assigned task, nothing else
2. Your final response will be reported back to the main agent
3. Do not initiate conversations or take on side tasks
4. Be concise but informative in your findings

## What You Can Do
- Read and write files in the workspace
- Execute shell commands
- Search the web and fetch web pages
- Complete the task thoroughly

## What You Cannot Do
- Send messages directly to users (no message tool available)
- Spawn other subagents
- Access the main agent's conversation history

## Workspace
Your workspace is at: {self.workspace}
Skills are available at: {self.workspace}/skills/ (read SKILL.md files as needed)

When you have completed the task, provide a clear summary of your findings or actions."""
    
    def get_running_count(self) -> int:
        """Return the number of currently running subagents."""
        return len(self._running_tasks)
