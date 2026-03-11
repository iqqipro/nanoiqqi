"""CLI commands for iqqibot."""

import asyncio
import os
import signal
import time
import threading
from pathlib import Path
import select
import sys

import typer
from rich.console import Console
from rich.markdown import Markdown
from rich.table import Table
from rich.text import Text

from prompt_toolkit import PromptSession
from prompt_toolkit.formatted_text import HTML
from prompt_toolkit.history import FileHistory
from prompt_toolkit.patch_stdout import patch_stdout

from nanobot import __version__, __logo__, __brand__
from nanobot.config.schema import Config

app = typer.Typer(
    name="iqqibot",
    help=f"{__logo__} iqqibot - Personal AI Assistant",
    no_args_is_help=True,
)

console = Console(color_system="truecolor")
EXIT_COMMANDS = {"exit", "quit", "/exit", "/quit", ":q"}

# ---------------------------------------------------------------------------
# CLI color palette — single source of truth for the whole interface
# ---------------------------------------------------------------------------
# Low/no red (R) in hex so terminals don't render as orange. Green bolt + yellow bolt.
# Green bolt: ASCII, cat, bot branding, success, links, tables
# Yellow bolt: user label ("You:"), warnings
# ---------------------------------------------------------------------------

_GREEN_BOLT = "#b7ff00"
_YELLOW_BOLT = "#f0fc08"
_BLACK = "#000000"

_BANNER = r"""
  ██╗ ██████╗  ██████╗ ██╗██████╗  ██████╗ ████████╗
  ██║██╔═══██╗██╔═══██╗██║██╔══██╗██╔═══██╗╚══██╔══╝
  ██║██║   ██║██║   ██║██║██████╔╝██║   ██║   ██║
  ██║██║▄▄ ██║██║▄▄ ██║██║██╔══██╗██║   ██║   ██║
  ██║╚██████╔╝╚██████╔╝██║██████╔╝╚██████╔╝   ██║
  ╚═╝ ╚══▀▀═╝  ╚══▀▀═╝ ╚═╝╚═════╝  ╚═════╝    ╚═╝
"""

_WELCOME_BOX = r"""
╭──────────────────────────────────────────────────╮
│          ⚡ Welcome to IQQIBOT!! ⚡              │
╰──────────────────────────────────────────────────╯
"""

_DIVIDER = "━" * 54

_THINKING_DOTS = ["   ", ".  ", ".. ", "..."]

_BANNER_ANIM_DELAY = 0.04


def _icon_with_label(
    label: str,
    *,
    icon: str = __logo__,
    fg: str = _GREEN_BOLT,
    bg: str | None = None,
) -> str:
    """Render a compact icon followed by a styled label."""
    if bg:
        icon_markup = f"[bold {_BLACK} on {bg}] {icon} [/bold {_BLACK} on {bg}]"
    else:
        icon_markup = f"[bold {fg}]{icon}[/bold {fg}]"
    return f"{icon_markup}  {label}"


def _print_banner(animated: bool | None = None) -> None:
    """Print welcome box + ASCII banner, animated."""
    if animated is None:
        try:
            animated = sys.stdout.isatty()
        except Exception:
            animated = False

    console.print()

    welcome_lines = _WELCOME_BOX.strip("\n").split("\n")
    for line in welcome_lines:
        console.print(f"[bold {_GREEN_BOLT}]{line}[/bold {_GREEN_BOLT}]")
        if animated:
            time.sleep(_BANNER_ANIM_DELAY)

    for line in _BANNER.strip("\n").split("\n"):
        console.print(f"[bold {_GREEN_BOLT}]{line}[/bold {_GREEN_BOLT}]")
        if animated:
            time.sleep(_BANNER_ANIM_DELAY)

    if animated:
        time.sleep(0.06)

    console.print(f"[bold {_GREEN_BOLT}]{_DIVIDER}[/bold {_GREEN_BOLT}]")
    console.print(f"[dim {_GREEN_BOLT}]  v{__version__}[/dim {_GREEN_BOLT}]")
    console.print()


def _styled(text: str) -> str:
    """Bot-side header: icon + branding."""
    label = f"[bold {_GREEN_BOLT}]{__logo__} {__brand__}[/bold {_GREEN_BOLT}] [dim {_GREEN_BOLT}]• {text}[/dim {_GREEN_BOLT}]"
    return _icon_with_label(label, fg=_GREEN_BOLT)

# ---------------------------------------------------------------------------
# CLI input: prompt_toolkit for editing, paste, history, and display
# ---------------------------------------------------------------------------

_PROMPT_SESSION: PromptSession | None = None
_SAVED_TERM_ATTRS = None  # original termios settings, restored on exit


def _flush_pending_tty_input() -> None:
    """Drop unread keypresses typed while the model was generating output."""
    try:
        fd = sys.stdin.fileno()
        if not os.isatty(fd):
            return
    except Exception:
        return

    try:
        import termios
        termios.tcflush(fd, termios.TCIFLUSH)
        return
    except Exception:
        pass

    try:
        while True:
            ready, _, _ = select.select([fd], [], [], 0)
            if not ready:
                break
            if not os.read(fd, 4096):
                break
    except Exception:
        return


def _restore_terminal() -> None:
    """Restore terminal to its original state (echo, line buffering, etc.)."""
    if _SAVED_TERM_ATTRS is None:
        return
    try:
        import termios
        termios.tcsetattr(sys.stdin.fileno(), termios.TCSADRAIN, _SAVED_TERM_ATTRS)
    except Exception:
        pass


def _init_prompt_session() -> None:
    """Create the prompt_toolkit session with persistent file history."""
    global _PROMPT_SESSION, _SAVED_TERM_ATTRS

    # Save terminal state so we can restore it on exit
    try:
        import termios
        _SAVED_TERM_ATTRS = termios.tcgetattr(sys.stdin.fileno())
    except Exception:
        pass

    history_file = Path.home() / ".nanobot" / "history" / "cli_history"
    history_file.parent.mkdir(parents=True, exist_ok=True)

    _PROMPT_SESSION = PromptSession(
        history=FileHistory(str(history_file)),
        enable_open_in_editor=False,
        multiline=False,   # Enter submits (single line mode)
    )


def _print_agent_response(response: str, render_markdown: bool) -> None:
    """Render assistant response: first line to the right of iqqibot, rest below."""
    content = (response or "").strip()
    lines = content.split("\n") if content else []
    first_line = lines[0] if lines else ""
    rest_lines = lines[1:]
    console.print()
    if first_line:
        label = f"[bold {_GREEN_BOLT}]{__brand__}[/bold {_GREEN_BOLT}] [dim {_GREEN_BOLT}]{first_line}[/dim {_GREEN_BOLT}]"
        console.print(_icon_with_label(label, fg=_GREEN_BOLT))
    else:
        console.print(_styled("online"))
    if rest_lines:
        rest_content = "\n".join(rest_lines)
        rest_body = Markdown(rest_content) if render_markdown else Text(rest_content)
        console.print(rest_body)
    console.print()


def _is_exit_command(command: str) -> bool:
    """Return True when input should end interactive chat."""
    return command.lower() in EXIT_COMMANDS


async def _read_interactive_input_async() -> str:
    """Prompt on same line as 'You' so the typed message appears to the right of You."""
    if _PROMPT_SESSION is None:
        raise RuntimeError("Call _init_prompt_session() first")
    console.print()
    try:
        with patch_stdout():
            return await _PROMPT_SESSION.prompt_async(
                HTML(f"<b fg='{_YELLOW_BOLT}'>⚡ You  ❯</b> "),
            )
    except EOFError as exc:
        raise KeyboardInterrupt from exc



def version_callback(value: bool):
    if value:
        _print_banner()
        console.print(f"  [bold {_GREEN_BOLT}]v{__version__}[/bold {_GREEN_BOLT}]")
        raise typer.Exit()


@app.callback()
def main(
    version: bool = typer.Option(
        None, "--version", "-v", callback=version_callback, is_eager=True
    ),
):
    """iqqibot - Personal AI Assistant."""
    pass


# ============================================================================
# Onboard / Setup
# ============================================================================


@app.command()
def onboard():
    """Initialize nanobot configuration and workspace."""
    from nanobot.config.loader import get_config_path, load_config, save_config
    from nanobot.config.schema import Config
    from nanobot.utils.helpers import get_workspace_path
    
    config_path = get_config_path()
    
    if config_path.exists():
        console.print(f"[bold {_GREEN_BOLT}]Config already exists at {config_path}[/bold {_GREEN_BOLT}]")
        console.print("  [bold]y[/bold] = overwrite with defaults (existing values will be lost)")
        console.print("  [bold]N[/bold] = refresh config, keeping existing values and adding new fields")
        if typer.confirm("Overwrite?"):
            config = Config()
            save_config(config)
            console.print(f"[bold {_GREEN_BOLT}]✓[/bold {_GREEN_BOLT}] Config reset to defaults at {config_path}")
        else:
            config = load_config()
            save_config(config)
            console.print(f"[bold {_GREEN_BOLT}]✓[/bold {_GREEN_BOLT}] Config refreshed at {config_path} (existing values preserved)")
    else:
        save_config(Config())
        console.print(f"[bold {_GREEN_BOLT}]✓[/bold {_GREEN_BOLT}] Created config at {config_path}")
    
    # Create workspace
    workspace = get_workspace_path()
    
    if not workspace.exists():
        workspace.mkdir(parents=True, exist_ok=True)
        console.print(f"[bold {_GREEN_BOLT}]✓[/bold {_GREEN_BOLT}] Created workspace at {workspace}")
    
    # Create default bootstrap files
    _create_workspace_templates(workspace)
    
    _print_banner()
    console.print(_styled("iqqibot is ready!"))
    console.print("\nNext steps:")
    console.print(f"  1. Add your API key to [bold {_GREEN_BOLT}]~/.nanobot/config.json[/bold {_GREEN_BOLT}]")
    console.print("     Get one at: https://openrouter.ai/keys")
    console.print(f"  2. Chat: [bold {_GREEN_BOLT}]nanobot agent -m \"Hello!\"[/bold {_GREEN_BOLT}]")
    console.print("\n[dim]Want Telegram/WhatsApp? See: https://github.com/HKUDS/nanobot#-chat-apps[/dim]")




def _create_workspace_templates(workspace: Path):
    """Create default workspace template files."""
    templates = {
        "AGENTS.md": """# Agent Instructions

You are a helpful AI assistant. Be concise, accurate, and friendly.

## Guidelines

- Always explain what you're doing before taking actions
- Ask for clarification when the request is ambiguous
- Use tools to help accomplish tasks
- Remember important information in memory/MEMORY.md; past events are logged in memory/HISTORY.md
""",
        "SOUL.md": """# Soul

I am iqqibot, a lightweight AI assistant.

## Personality

- Helpful and friendly
- Concise and to the point
- Curious and eager to learn

## Values

- Accuracy over speed
- User privacy and safety
- Transparency in actions
""",
        "USER.md": """# User

Information about the user goes here.

## Preferences

- Communication style: (casual/formal)
- Timezone: (your timezone)
- Language: (your preferred language)
""",
    }
    
    for filename, content in templates.items():
        file_path = workspace / filename
        if not file_path.exists():
            file_path.write_text(content, encoding="utf-8")
            console.print(f"  [dim]Created {filename}[/dim]")
    
    # Create memory directory and MEMORY.md
    memory_dir = workspace / "memory"
    memory_dir.mkdir(exist_ok=True)
    memory_file = memory_dir / "MEMORY.md"
    if not memory_file.exists():
        memory_file.write_text("""# Long-term Memory

This file stores important information that should persist across sessions.

## User Information

(Important facts about the user)

## Preferences

(User preferences learned over time)

## Important Notes

(Things to remember)
""", encoding="utf-8")
        console.print("  [dim]Created memory/MEMORY.md[/dim]")
    
    history_file = memory_dir / "HISTORY.md"
    if not history_file.exists():
        history_file.write_text("", encoding="utf-8")
        console.print("  [dim]Created memory/HISTORY.md[/dim]")

    # Create skills directory for custom user skills
    skills_dir = workspace / "skills"
    skills_dir.mkdir(exist_ok=True)


def _make_provider(config: Config):
    """Create the appropriate LLM provider from config, wrapped with routing if configured."""
    from nanobot.providers.litellm_provider import LiteLLMProvider
    from nanobot.providers.openai_codex_provider import OpenAICodexProvider
    from nanobot.providers.custom_provider import CustomProvider
    from nanobot.providers.routing import RoutingProvider

    routing = config.routing
    model = config.agents.defaults.model

    # Resolve default model through aliases so provider matching works correctly
    if routing.aliases:
        model = routing.aliases.get(model.lower(), model)

    provider_name = config.get_provider_name(model)
    p = config.get_provider(model)

    # OpenAI Codex (OAuth)
    if provider_name == "openai_codex" or model.startswith("openai-codex/"):
        inner = OpenAICodexProvider(default_model=model)
    elif provider_name == "custom":
        inner = CustomProvider(
            api_key=p.api_key if p else "no-key",
            api_base=config.get_api_base(model) or "http://localhost:8000/v1",
            default_model=model,
        )
    else:
        from nanobot.providers.registry import find_by_name
        spec = find_by_name(provider_name)
        if not model.startswith("bedrock/") and not (p and p.api_key) and not (spec and spec.is_oauth):
            console.print("[red]Error: No API key configured.[/red]")
            console.print("Set one in ~/.nanobot/config.json under providers section")
            raise typer.Exit(1)

        inner = LiteLLMProvider(
            api_key=p.api_key if p else None,
            api_base=config.get_api_base(model),
            default_model=model,
            extra_headers=p.extra_headers if p else None,
            provider_name=provider_name,
        )

    # Smart routing: only when tools.smart_router.api_key is set (Artificial Analysis API).
    # Model data is loaded from AA; routing.* (policy, judge_model, weights) still apply.
    smart_router_cfg = getattr(config.tools, "smart_router", None)
    aa_api_key = (smart_router_cfg.api_key or "").strip() if smart_router_cfg else ""
    if aa_api_key:
        from nanobot.providers.smart_router import SmartRouter
        from nanobot.providers.router_metrics import RouterMetrics
        from nanobot.providers.artificial_analysis import fetch_models, fetch_top_agentic_models
        metrics_path = config.workspace_path / ".nanobot" / "router_metrics.json"
        metrics = RouterMetrics(metrics_path)
        aa_base = (smart_router_cfg.api_base or "").strip() or "https://artificialanalysis.ai/api/v2"
        openrouter_key = (getattr(config.providers.openrouter, "api_key", None) or "").strip()
        top_n = int(getattr(smart_router_cfg, "top_agentic_n", 15) or 15)
        capabilities_top_agentic = fetch_top_agentic_models(
            aa_api_key,
            aa_base,
            top_n=top_n,
            use_cache=True,
            openrouter_api_key=openrouter_key or None,
        )
        subagent_capabilities = fetch_models(
            aa_api_key,
            aa_base,
            use_cache=True,
            openrouter_api_key=openrouter_key or None,
        )
        exclude_models = getattr(smart_router_cfg, "exclude_models", None) or getattr(routing, "exclude_models", None) or None
        router = SmartRouter(
            inner,
            policy=getattr(routing, "policy", "balanced"),
            candidate_models=None,
            judge_model=getattr(routing, "judge_model", "") or "",
            weights_override=getattr(routing, "weights", None) or None,
            metrics=metrics,
            default_model_hint=model,
            capabilities_from_api=capabilities_top_agentic if capabilities_top_agentic else None,
            subagent_capabilities_from_api=subagent_capabilities if subagent_capabilities else None,
            max_cost_per_request_usd=float(getattr(smart_router_cfg, "max_cost_per_request_usd", 0) or 0),
            exclude_models=exclude_models,
        )
        return router, router

    if routing.aliases or routing.fallback_models:
        return RoutingProvider(
            inner,
            aliases=routing.aliases or None,
            fallback_models=routing.fallback_models or None,
        ), None
    return inner, None


def _make_activity_sink(config: Config):
    """Create activity sink for Brain Office (always on). URL from config.brain_office."""
    from nanobot.agent.activity_sink import make_activity_sink
    bo = getattr(config, "brain_office", None)
    url = (bo.url or "http://localhost:8765").strip() if bo else "http://localhost:8765"
    return make_activity_sink(url)


def _make_brain_office_bridge(bus, config, agent_loop):
    """Create the optional Brain Office command bridge."""
    from nanobot.brain_office.bridge import BrainOfficeBridge

    bo = getattr(config, "brain_office", None)
    url = (bo.url or "http://localhost:8765").strip() if bo else "http://localhost:8765"

    async def _spawn(task: str, label: str | None, chat_id: str) -> str:
        return await agent_loop.subagents.spawn(
            task=task,
            label=label,
            origin_channel="brain-office",
            origin_chat_id=chat_id,
        )

    return BrainOfficeBridge(bus=bus, base_url=url, spawn_callback=_spawn)


# ============================================================================
# Gateway / Server
# ============================================================================


@app.command()
def gateway(
    port: int = typer.Option(18790, "--port", "-p", help="Gateway port"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose output"),
):
    """Start the iqqibot gateway."""
    from nanobot.config.loader import load_config, get_data_dir
    from nanobot.bus.queue import MessageBus
    from nanobot.agent.loop import AgentLoop
    from nanobot.channels.manager import ChannelManager
    from nanobot.session.manager import SessionManager
    from nanobot.cron.service import CronService
    from nanobot.cron.types import CronJob
    from nanobot.heartbeat.service import HeartbeatService
    
    if verbose:
        import logging
        logging.basicConfig(level=logging.DEBUG)
    
    _print_banner()
    console.print(_styled(f"Starting gateway on port {port}..."))
    
    config = load_config()
    bus = MessageBus()
    provider, subagent_provider = _make_provider(config)
    session_manager = SessionManager(config.workspace_path)
    
    # Create cron service first (callback set after agent creation)
    cron_store_path = get_data_dir() / "cron" / "jobs.json"
    cron = CronService(cron_store_path)
    
    # Create agent with cron service
    _tc_model = (config.agents.defaults.tool_calling_model or "").strip() or None
    if _tc_model and config.routing.aliases:
        _tc_model = config.routing.aliases.get(_tc_model.lower(), _tc_model)
    agent = AgentLoop(
        bus=bus,
        provider=provider,
        workspace=config.workspace_path,
        model=config.agents.defaults.model,
        tool_calling_model=_tc_model,
        temperature=config.agents.defaults.temperature,
        max_tokens=config.agents.defaults.max_tokens,
        max_iterations=config.agents.defaults.max_tool_iterations,
        memory_window=config.agents.defaults.memory_window,
        brave_api_key=config.tools.web.search.api_key or None,
        exec_config=config.tools.exec,
        cron_service=cron,
        restrict_to_workspace=config.tools.restrict_to_workspace,
        session_manager=session_manager,
        mcp_servers=config.tools.mcp_servers,
        image_gen_api_key=config.providers.openrouter.api_key or None,
        image_gen_model=config.tools.image.model or None,
        subagent_provider=subagent_provider,
        subagent_model=(config.agents.defaults.subagent_model or "").strip() or None,
        leads_mx_token=config.tools.leads_mx.token or None,
        activity_sink=_make_activity_sink(config),
    )

    # Set cron callback (needs agent)
    async def on_cron_job(job: CronJob) -> str | None:
        """Execute a cron job through the agent."""
        response = await agent.process_direct(
            job.payload.message,
            session_key=f"cron:{job.id}",
            channel=job.payload.channel or "cli",
            chat_id=job.payload.to or "direct",
        )
        if job.payload.deliver and job.payload.to:
            from nanobot.bus.events import OutboundMessage
            await bus.publish_outbound(OutboundMessage(
                channel=job.payload.channel or "cli",
                chat_id=job.payload.to,
                content=response or ""
            ))
        return response
    cron.on_job = on_cron_job
    
    # Create heartbeat service
    routing = config.routing
    hb_model = routing.heartbeat_model or None
    hb_interval = routing.heartbeat_interval_s or 30 * 60

    async def on_heartbeat(prompt: str, model: str | None = None) -> str:
        """Execute heartbeat through the agent."""
        return await agent.process_direct(prompt, session_key="heartbeat", model=model)
    
    heartbeat = HeartbeatService(
        workspace=config.workspace_path,
        on_heartbeat=on_heartbeat,
        interval_s=hb_interval,
        enabled=True,
        model=hb_model,
    )
    
    brain_office_bridge = _make_brain_office_bridge(bus, config, agent)

    # Create channel manager
    channels = ChannelManager(
        config,
        bus,
        custom_dispatchers={"brain-office": brain_office_bridge.dispatch_outbound},
    )
    
    if channels.enabled_channels:
        console.print(f"[bold {_GREEN_BOLT}]✓[/bold {_GREEN_BOLT}] Channels enabled: {', '.join(channels.enabled_channels)}")
    else:
        console.print(f"[bold {_YELLOW_BOLT}]Warning: No channels enabled[/bold {_YELLOW_BOLT}]")
    
    cron_status = cron.status()
    if cron_status["jobs"] > 0:
        console.print(f"[bold {_GREEN_BOLT}]✓[/bold {_GREEN_BOLT}] Cron: {cron_status['jobs']} scheduled jobs")
    
    hb_min = hb_interval // 60
    hb_model_label = f" ({hb_model})" if hb_model else ""
    console.print(f"[bold {_GREEN_BOLT}]✓[/bold {_GREEN_BOLT}] Heartbeat: every {hb_min}m{hb_model_label}")
    
    async def run():
        try:
            await cron.start()
            await heartbeat.start()
            await asyncio.gather(
                agent.run(),
                channels.start_all(),
                brain_office_bridge.run(),
            )
        except KeyboardInterrupt:
            console.print("\nShutting down...")
        finally:
            await agent.close_mcp()
            await brain_office_bridge.aclose()
            heartbeat.stop()
            cron.stop()
            agent.stop()
            await channels.stop_all()
    
    asyncio.run(run())




# ============================================================================
# Agent Commands
# ============================================================================


@app.command()
def agent(
    message: str = typer.Option(None, "--message", "-m", help="Message to send to the agent"),
    session_id: str = typer.Option("cli:direct", "--session", "-s", help="Session ID"),
    markdown: bool = typer.Option(True, "--markdown/--no-markdown", help="Render assistant output as Markdown"),
    logs: bool = typer.Option(False, "--logs/--no-logs", help="Show iqqibot runtime logs during chat"),
):
    """Interact with the agent directly."""
    from nanobot.config.loader import load_config, get_data_dir
    from nanobot.bus.queue import MessageBus
    from nanobot.agent.loop import AgentLoop
    from nanobot.cron.service import CronService
    from loguru import logger
    
    config = load_config()
    
    bus = MessageBus()
    provider, subagent_provider = _make_provider(config)

    # Create cron service for tool usage (no callback needed for CLI unless running)
    cron_store_path = get_data_dir() / "cron" / "jobs.json"
    cron = CronService(cron_store_path)

    if logs:
        logger.enable("nanobot")
    else:
        logger.disable("nanobot")
    
    _tc_model = (config.agents.defaults.tool_calling_model or "").strip() or None
    if _tc_model and config.routing.aliases:
        _tc_model = config.routing.aliases.get(_tc_model.lower(), _tc_model)
    agent_loop = AgentLoop(
        bus=bus,
        provider=provider,
        workspace=config.workspace_path,
        model=config.agents.defaults.model,
        tool_calling_model=_tc_model,
        temperature=config.agents.defaults.temperature,
        max_tokens=config.agents.defaults.max_tokens,
        max_iterations=config.agents.defaults.max_tool_iterations,
        memory_window=config.agents.defaults.memory_window,
        brave_api_key=config.tools.web.search.api_key or None,
        exec_config=config.tools.exec,
        cron_service=cron,
        restrict_to_workspace=config.tools.restrict_to_workspace,
        mcp_servers=config.tools.mcp_servers,
        image_gen_api_key=config.providers.openrouter.api_key or None,
        image_gen_model=config.tools.image.model or None,
        subagent_provider=subagent_provider,
        subagent_model=(config.agents.defaults.subagent_model or "").strip() or None,
        leads_mx_token=config.tools.leads_mx.token or None,
        activity_sink=_make_activity_sink(config),
    )
    brain_office_bridge = _make_brain_office_bridge(bus, config, agent_loop)

    # Animated thinking indicator (single line)
    class _ThinkingIndicator:
        """Context manager: compact icon + dots on one line."""
        def __init__(self):
            self._stop = threading.Event()
            self._thread: threading.Thread | None = None

        _NUM_LINES = 1

        def __enter__(self):
            self._stop.clear()
            console.print()
            self._thread = threading.Thread(target=self._animate, daemon=True)
            self._thread.start()
            return self

        def __exit__(self, *_):
            self._stop.set()
            if self._thread:
                self._thread.join(timeout=1.0)
            sys.stdout.write(f"\033[{self._NUM_LINES}A\033[J")
            sys.stdout.flush()

        def _animate(self):
            dot_idx = 0
            while not self._stop.is_set():
                dots = _THINKING_DOTS[dot_idx % len(_THINKING_DOTS)]
                label = f"[bold {_GREEN_BOLT}]{__brand__}[/bold {_GREEN_BOLT}] [dim {_GREEN_BOLT}]is thinking{dots}[/dim {_GREEN_BOLT}]"
                if dot_idx > 0:
                    sys.stdout.write(f"\033[{self._NUM_LINES}A\033[J")
                console.print(_icon_with_label(label, fg=_GREEN_BOLT))
                dot_idx += 1
                self._stop.wait(0.4)

    def _thinking_ctx():
        if logs:
            from contextlib import nullcontext
            return nullcontext()
        return _ThinkingIndicator()

    async def _cli_progress(content: str) -> None:
        console.print(f"  [dim {_GREEN_BOLT}]↳[/dim {_GREEN_BOLT}] [dim {_GREEN_BOLT}]{content}[/dim {_GREEN_BOLT}]")

    if message:
        # Single message mode — direct call, no bus needed
        async def run_once():
            with _thinking_ctx():
                response = await agent_loop.process_direct(message, session_id, on_progress=_cli_progress)
            _print_agent_response(response, render_markdown=markdown)
            await agent_loop.close_mcp()

        asyncio.run(run_once())
    else:
        # Interactive mode — route through bus like other channels
        from nanobot.bus.events import InboundMessage
        _init_prompt_session()
        _print_banner(animated=True)
        console.print(_styled("Interactive mode"))
        console.print(f"[dim {_GREEN_BOLT}]  type exit or Ctrl+C to quit[/dim {_GREEN_BOLT}]\n")

        if ":" in session_id:
            cli_channel, cli_chat_id = session_id.split(":", 1)
        else:
            cli_channel, cli_chat_id = "cli", session_id

        def _exit_on_sigint(signum, frame):
            _restore_terminal()
            console.print(f"\n[bold {_GREEN_BOLT}]Goodbye! ⚡[/bold {_GREEN_BOLT}]")
            os._exit(0)

        signal.signal(signal.SIGINT, _exit_on_sigint)

        async def run_interactive():
            bus_task = asyncio.create_task(agent_loop.run())
            brain_office_task = asyncio.create_task(brain_office_bridge.run())
            turn_done = asyncio.Event()
            turn_done.set()
            turn_response: list[str] = []

            async def _consume_outbound():
                while True:
                    try:
                        msg = await asyncio.wait_for(bus.consume_outbound(), timeout=1.0)
                        if msg.channel == "brain-office":
                            await brain_office_bridge.dispatch_outbound(msg)
                            continue
                        if msg.metadata.get("_progress"):
                            console.print(f"  [dim {_GREEN_BOLT}]↳[/dim {_GREEN_BOLT}] [dim {_GREEN_BOLT}]{msg.content}[/dim {_GREEN_BOLT}]")
                        elif not turn_done.is_set():
                            if msg.content:
                                turn_response.append(msg.content)
                            turn_done.set()
                        elif msg.content:
                            console.print()
                            _print_agent_response(msg.content, render_markdown=markdown)
                    except asyncio.TimeoutError:
                        continue
                    except asyncio.CancelledError:
                        break

            outbound_task = asyncio.create_task(_consume_outbound())

            try:
                while True:
                    try:
                        _flush_pending_tty_input()
                        user_input = await _read_interactive_input_async()
                        command = user_input.strip()
                        if not command:
                            continue

                        if _is_exit_command(command):
                            _restore_terminal()
                            console.print(f"\n[bold {_GREEN_BOLT}]Goodbye! ⚡[/bold {_GREEN_BOLT}]")
                            break

                        turn_done.clear()
                        turn_response.clear()

                        await bus.publish_inbound(InboundMessage(
                            channel=cli_channel,
                            sender_id="user",
                            chat_id=cli_chat_id,
                            content=user_input,
                        ))

                        with _thinking_ctx():
                            await turn_done.wait()

                        if turn_response:
                            _print_agent_response(turn_response[0], render_markdown=markdown)
                    except KeyboardInterrupt:
                        _restore_terminal()
                        console.print(f"\n[bold {_GREEN_BOLT}]Goodbye! ⚡[/bold {_GREEN_BOLT}]")
                        break
                    except EOFError:
                        _restore_terminal()
                        console.print(f"\n[bold {_GREEN_BOLT}]Goodbye! ⚡[/bold {_GREEN_BOLT}]")
                        break
            finally:
                agent_loop.stop()
                outbound_task.cancel()
                brain_office_task.cancel()
                await asyncio.gather(bus_task, outbound_task, brain_office_task, return_exceptions=True)
                await brain_office_bridge.aclose()
                await agent_loop.close_mcp()

        asyncio.run(run_interactive())


# ============================================================================
# Channel Commands
# ============================================================================


channels_app = typer.Typer(help="Manage channels")
app.add_typer(channels_app, name="channels")


@channels_app.command("status")
def channels_status():
    """Show channel status."""
    from nanobot.config.loader import load_config

    config = load_config()

    table = Table(title="Channel Status")
    table.add_column("Channel", style=_GREEN_BOLT)
    table.add_column("Enabled", style=_GREEN_BOLT)
    table.add_column("Configuration", style=_GREEN_BOLT)

    # WhatsApp
    wa = config.channels.whatsapp
    table.add_row(
        "WhatsApp",
        "✓" if wa.enabled else "✗",
        wa.bridge_url
    )

    dc = config.channels.discord
    table.add_row(
        "Discord",
        "✓" if dc.enabled else "✗",
        dc.gateway_url
    )

    # Feishu
    fs = config.channels.feishu
    fs_config = f"app_id: {fs.app_id[:10]}..." if fs.app_id else "[dim]not configured[/dim]"
    table.add_row(
        "Feishu",
        "✓" if fs.enabled else "✗",
        fs_config
    )

    # Mochat
    mc = config.channels.mochat
    mc_base = mc.base_url or "[dim]not configured[/dim]"
    table.add_row(
        "Mochat",
        "✓" if mc.enabled else "✗",
        mc_base
    )
    
    # Telegram
    tg = config.channels.telegram
    tg_config = f"token: {tg.token[:10]}..." if tg.token else "[dim]not configured[/dim]"
    table.add_row(
        "Telegram",
        "✓" if tg.enabled else "✗",
        tg_config
    )

    # Slack
    slack = config.channels.slack
    slack_config = "socket" if slack.app_token and slack.bot_token else "[dim]not configured[/dim]"
    table.add_row(
        "Slack",
        "✓" if slack.enabled else "✗",
        slack_config
    )

    # DingTalk
    dt = config.channels.dingtalk
    dt_config = f"client_id: {dt.client_id[:10]}..." if dt.client_id else "[dim]not configured[/dim]"
    table.add_row(
        "DingTalk",
        "✓" if dt.enabled else "✗",
        dt_config
    )

    # QQ
    qq = config.channels.qq
    qq_config = f"app_id: {qq.app_id[:10]}..." if qq.app_id else "[dim]not configured[/dim]"
    table.add_row(
        "QQ",
        "✓" if qq.enabled else "✗",
        qq_config
    )

    # Email
    em = config.channels.email
    em_config = em.imap_host if em.imap_host else "[dim]not configured[/dim]"
    table.add_row(
        "Email",
        "✓" if em.enabled else "✗",
        em_config
    )

    console.print(table)


def _get_bridge_dir() -> Path:
    """Get the bridge directory, setting it up if needed."""
    import shutil
    import subprocess
    
    # User's bridge location
    user_bridge = Path.home() / ".nanobot" / "bridge"
    
    # Check if already built
    if (user_bridge / "dist" / "index.js").exists():
        return user_bridge
    
    # Check for npm
    if not shutil.which("npm"):
        console.print("[red]npm not found. Please install Node.js >= 18.[/red]")
        raise typer.Exit(1)
    
    # Find source bridge: first check package data, then source dir
    pkg_bridge = Path(__file__).parent.parent / "bridge"  # nanobot/bridge (installed)
    src_bridge = Path(__file__).parent.parent.parent / "bridge"  # repo root/bridge (dev)
    
    source = None
    if (pkg_bridge / "package.json").exists():
        source = pkg_bridge
    elif (src_bridge / "package.json").exists():
        source = src_bridge
    
    if not source:
        console.print("[red]Bridge source not found.[/red]")
        console.print("Try reinstalling: pip install --force-reinstall nanobot")
        raise typer.Exit(1)
    
    console.print(_styled("Setting up bridge..."))
    
    # Copy to user directory
    user_bridge.parent.mkdir(parents=True, exist_ok=True)
    if user_bridge.exists():
        shutil.rmtree(user_bridge)
    shutil.copytree(source, user_bridge, ignore=shutil.ignore_patterns("node_modules", "dist"))
    
    # Install and build
    try:
        console.print("  Installing dependencies...")
        subprocess.run(["npm", "install"], cwd=user_bridge, check=True, capture_output=True)
        
        console.print("  Building...")
        subprocess.run(["npm", "run", "build"], cwd=user_bridge, check=True, capture_output=True)
        
        console.print(f"[bold {_GREEN_BOLT}]✓[/bold {_GREEN_BOLT}] Bridge ready\n")
    except subprocess.CalledProcessError as e:
        console.print(f"[red]Build failed: {e}[/red]")
        if e.stderr:
            console.print(f"[dim]{e.stderr.decode()[:500]}[/dim]")
        raise typer.Exit(1)
    
    return user_bridge


@channels_app.command("login")
def channels_login():
    """Link device via QR code."""
    import subprocess
    from nanobot.config.loader import load_config
    
    config = load_config()
    bridge_dir = _get_bridge_dir()
    
    console.print(_styled("Starting bridge..."))
    console.print("Scan the QR code to connect.\n")
    
    env = {**os.environ}
    if config.channels.whatsapp.bridge_token:
        env["BRIDGE_TOKEN"] = config.channels.whatsapp.bridge_token
    
    try:
        subprocess.run(["npm", "start"], cwd=bridge_dir, check=True, env=env)
    except subprocess.CalledProcessError as e:
        console.print(f"[red]Bridge failed: {e}[/red]")
    except FileNotFoundError:
        console.print("[red]npm not found. Please install Node.js.[/red]")


# ============================================================================
# Cron Commands
# ============================================================================

cron_app = typer.Typer(help="Manage scheduled tasks")
app.add_typer(cron_app, name="cron")


@cron_app.command("list")
def cron_list(
    all: bool = typer.Option(False, "--all", "-a", help="Include disabled jobs"),
):
    """List scheduled jobs."""
    from nanobot.config.loader import get_data_dir
    from nanobot.cron.service import CronService
    
    store_path = get_data_dir() / "cron" / "jobs.json"
    service = CronService(store_path)
    
    jobs = service.list_jobs(include_disabled=all)
    
    if not jobs:
        console.print("No scheduled jobs.")
        return
    
    table = Table(title="Scheduled Jobs")
    table.add_column("ID", style=_GREEN_BOLT)
    table.add_column("Name")
    table.add_column("Schedule")
    table.add_column("Status")
    table.add_column("Next Run")
    
    import time
    from datetime import datetime as _dt
    from zoneinfo import ZoneInfo
    for job in jobs:
        # Format schedule
        if job.schedule.kind == "every":
            sched = f"every {(job.schedule.every_ms or 0) // 1000}s"
        elif job.schedule.kind == "cron":
            sched = f"{job.schedule.expr or ''} ({job.schedule.tz})" if job.schedule.tz else (job.schedule.expr or "")
        else:
            sched = "one-time"
        
        # Format next run
        next_run = ""
        if job.state.next_run_at_ms:
            ts = job.state.next_run_at_ms / 1000
            try:
                tz = ZoneInfo(job.schedule.tz) if job.schedule.tz else None
                next_run = _dt.fromtimestamp(ts, tz).strftime("%Y-%m-%d %H:%M")
            except Exception:
                next_run = time.strftime("%Y-%m-%d %H:%M", time.localtime(ts))
        
        status = f"[bold {_GREEN_BOLT}]enabled[/bold {_GREEN_BOLT}]" if job.enabled else "[dim]disabled[/dim]"
        
        table.add_row(job.id, job.name, sched, status, next_run)
    
    console.print(table)


@cron_app.command("add")
def cron_add(
    name: str = typer.Option(..., "--name", "-n", help="Job name"),
    message: str = typer.Option(..., "--message", "-m", help="Message for agent"),
    every: int = typer.Option(None, "--every", "-e", help="Run every N seconds"),
    cron_expr: str = typer.Option(None, "--cron", "-c", help="Cron expression (e.g. '0 9 * * *')"),
    tz: str | None = typer.Option(None, "--tz", help="IANA timezone for cron (e.g. 'America/Vancouver')"),
    at: str = typer.Option(None, "--at", help="Run once at time (ISO format)"),
    deliver: bool = typer.Option(False, "--deliver", "-d", help="Deliver response to channel"),
    to: str = typer.Option(None, "--to", help="Recipient for delivery"),
    channel: str = typer.Option(None, "--channel", help="Channel for delivery (e.g. 'telegram', 'whatsapp')"),
):
    """Add a scheduled job."""
    from nanobot.config.loader import get_data_dir
    from nanobot.cron.service import CronService
    from nanobot.cron.types import CronSchedule
    
    if tz and not cron_expr:
        console.print("[red]Error: --tz can only be used with --cron[/red]")
        raise typer.Exit(1)

    # Determine schedule type
    if every:
        schedule = CronSchedule(kind="every", every_ms=every * 1000)
    elif cron_expr:
        schedule = CronSchedule(kind="cron", expr=cron_expr, tz=tz)
    elif at:
        import datetime
        dt = datetime.datetime.fromisoformat(at)
        schedule = CronSchedule(kind="at", at_ms=int(dt.timestamp() * 1000))
    else:
        console.print("[red]Error: Must specify --every, --cron, or --at[/red]")
        raise typer.Exit(1)
    
    store_path = get_data_dir() / "cron" / "jobs.json"
    service = CronService(store_path)
    
    try:
        job = service.add_job(
            name=name,
            schedule=schedule,
            message=message,
            deliver=deliver,
            to=to,
            channel=channel,
        )
    except ValueError as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1) from e

    console.print(f"[bold {_GREEN_BOLT}]✓[/bold {_GREEN_BOLT}] Added job '{job.name}' ({job.id})")


@cron_app.command("remove")
def cron_remove(
    job_id: str = typer.Argument(..., help="Job ID to remove"),
):
    """Remove a scheduled job."""
    from nanobot.config.loader import get_data_dir
    from nanobot.cron.service import CronService
    
    store_path = get_data_dir() / "cron" / "jobs.json"
    service = CronService(store_path)
    
    if service.remove_job(job_id):
        console.print(f"[bold {_GREEN_BOLT}]✓[/bold {_GREEN_BOLT}] Removed job {job_id}")
    else:
        console.print(f"[red]Job {job_id} not found[/red]")


@cron_app.command("enable")
def cron_enable(
    job_id: str = typer.Argument(..., help="Job ID"),
    disable: bool = typer.Option(False, "--disable", help="Disable instead of enable"),
):
    """Enable or disable a job."""
    from nanobot.config.loader import get_data_dir
    from nanobot.cron.service import CronService
    
    store_path = get_data_dir() / "cron" / "jobs.json"
    service = CronService(store_path)
    
    job = service.enable_job(job_id, enabled=not disable)
    if job:
        status = "disabled" if disable else "enabled"
        console.print(f"[bold {_GREEN_BOLT}]✓[/bold {_GREEN_BOLT}] Job '{job.name}' {status}")
    else:
        console.print(f"[red]Job {job_id} not found[/red]")


@cron_app.command("run")
def cron_run(
    job_id: str = typer.Argument(..., help="Job ID to run"),
    force: bool = typer.Option(False, "--force", "-f", help="Run even if disabled"),
):
    """Manually run a job."""
    from loguru import logger
    from nanobot.config.loader import load_config, get_data_dir
    from nanobot.cron.service import CronService
    from nanobot.cron.types import CronJob
    from nanobot.bus.queue import MessageBus
    from nanobot.agent.loop import AgentLoop
    logger.disable("nanobot")

    config = load_config()
    provider, subagent_provider = _make_provider(config)
    bus = MessageBus()
    _tc_model = (config.agents.defaults.tool_calling_model or "").strip() or None
    if _tc_model and config.routing.aliases:
        _tc_model = config.routing.aliases.get(_tc_model.lower(), _tc_model)
    agent_loop = AgentLoop(
        bus=bus,
        provider=provider,
        workspace=config.workspace_path,
        model=config.agents.defaults.model,
        tool_calling_model=_tc_model,
        temperature=config.agents.defaults.temperature,
        max_tokens=config.agents.defaults.max_tokens,
        max_iterations=config.agents.defaults.max_tool_iterations,
        memory_window=config.agents.defaults.memory_window,
        brave_api_key=config.tools.web.search.api_key or None,
        exec_config=config.tools.exec,
        restrict_to_workspace=config.tools.restrict_to_workspace,
        mcp_servers=config.tools.mcp_servers,
        image_gen_api_key=config.providers.openrouter.api_key or None,
        image_gen_model=config.tools.image.model or None,
        subagent_provider=subagent_provider,
        subagent_model=(config.agents.defaults.subagent_model or "").strip() or None,
        leads_mx_token=config.tools.leads_mx.token or None,
        activity_sink=_make_activity_sink(config),
    )

    store_path = get_data_dir() / "cron" / "jobs.json"
    service = CronService(store_path)

    result_holder = []

    async def on_job(job: CronJob) -> str | None:
        response = await agent_loop.process_direct(
            job.payload.message,
            session_key=f"cron:{job.id}",
            channel=job.payload.channel or "cli",
            chat_id=job.payload.to or "direct",
        )
        result_holder.append(response)
        return response

    service.on_job = on_job

    async def run():
        return await service.run_job(job_id, force=force)

    if asyncio.run(run()):
        console.print(f"[bold {_GREEN_BOLT}]✓[/bold {_GREEN_BOLT}] Job executed")
        if result_holder:
            _print_agent_response(result_holder[0], render_markdown=True)
    else:
        console.print(f"[red]Failed to run job {job_id}[/red]")


# ============================================================================
# Status Commands
# ============================================================================


@app.command()
def status():
    """Show iqqibot status."""
    from nanobot.config.loader import load_config, get_config_path

    config_path = get_config_path()
    config = load_config()
    workspace = config.workspace_path

    _print_banner()
    console.print(_styled("Status") + "\n")

    console.print(f"Config: {config_path} {'[bold {_GREEN_BOLT}]✓[/bold {_GREEN_BOLT}]' if config_path.exists() else '[red]✗[/red]'}")
    console.print(f"Workspace: {workspace} {'[bold {_GREEN_BOLT}]✓[/bold {_GREEN_BOLT}]' if workspace.exists() else '[red]✗[/red]'}")

    if config_path.exists():
        from nanobot.providers.registry import PROVIDERS

        console.print(f"Model: {config.agents.defaults.model}")
        
        # Check API keys from registry
        for spec in PROVIDERS:
            p = getattr(config.providers, spec.name, None)
            if p is None:
                continue
            if spec.is_oauth:
                console.print(f"{spec.label}: [bold {_GREEN_BOLT}]✓ (OAuth)[/bold {_GREEN_BOLT}]")
            elif spec.is_local:
                # Local deployments show api_base instead of api_key
                if p.api_base:
                    console.print(f"{spec.label}: [bold {_GREEN_BOLT}]✓ {p.api_base}[/bold {_GREEN_BOLT}]")
                else:
                    console.print(f"{spec.label}: [dim]not set[/dim]")
            else:
                has_key = bool(p.api_key)
                console.print(f"{spec.label}: {'[bold {_GREEN_BOLT}]✓[/bold {_GREEN_BOLT}]' if has_key else '[dim]not set[/dim]'}")


# ============================================================================
# OAuth Login
# ============================================================================

provider_app = typer.Typer(help="Manage providers")
app.add_typer(provider_app, name="provider")


_LOGIN_HANDLERS: dict[str, callable] = {}


def _register_login(name: str):
    def decorator(fn):
        _LOGIN_HANDLERS[name] = fn
        return fn
    return decorator


@provider_app.command("login")
def provider_login(
    provider: str = typer.Argument(..., help="OAuth provider (e.g. 'openai-codex', 'github-copilot')"),
):
    """Authenticate with an OAuth provider."""
    from nanobot.providers.registry import PROVIDERS

    key = provider.replace("-", "_")
    spec = next((s for s in PROVIDERS if s.name == key and s.is_oauth), None)
    if not spec:
        names = ", ".join(s.name.replace("_", "-") for s in PROVIDERS if s.is_oauth)
        console.print(f"[red]Unknown OAuth provider: {provider}[/red]  Supported: {names}")
        raise typer.Exit(1)

    handler = _LOGIN_HANDLERS.get(spec.name)
    if not handler:
        console.print(f"[red]Login not implemented for {spec.label}[/red]")
        raise typer.Exit(1)

    console.print(_styled(f"OAuth Login - {spec.label}") + "\n")
    handler()


@_register_login("openai_codex")
def _login_openai_codex() -> None:
    try:
        from oauth_cli_kit import get_token, login_oauth_interactive
        token = None
        try:
            token = get_token()
        except Exception:
            pass
        if not (token and token.access):
            console.print(f"[bold {_GREEN_BOLT}]Starting interactive OAuth login...[/bold {_GREEN_BOLT}]\n")
            token = login_oauth_interactive(
                print_fn=lambda s: console.print(s),
                prompt_fn=lambda s: typer.prompt(s),
            )
        if not (token and token.access):
            console.print("[red]✗ Authentication failed[/red]")
            raise typer.Exit(1)
        console.print(f"[bold {_GREEN_BOLT}]✓ Authenticated with OpenAI Codex[/bold {_GREEN_BOLT}]  [dim]{token.account_id}[/dim]")
    except ImportError:
        console.print("[red]oauth_cli_kit not installed. Run: pip install oauth-cli-kit[/red]")
        raise typer.Exit(1)


@_register_login("github_copilot")
def _login_github_copilot() -> None:
    import asyncio

    console.print(f"[bold {_GREEN_BOLT}]Starting GitHub Copilot device flow...[/bold {_GREEN_BOLT}]\n")

    async def _trigger():
        from litellm import acompletion
        await acompletion(model="github_copilot/gpt-4o", messages=[{"role": "user", "content": "hi"}], max_tokens=1)

    try:
        asyncio.run(_trigger())
        console.print(f"[bold {_GREEN_BOLT}]✓ Authenticated with GitHub Copilot[/bold {_GREEN_BOLT}]")
    except Exception as e:
        console.print(f"[red]Authentication error: {e}[/red]")
        raise typer.Exit(1)


if __name__ == "__main__":
    app()
