"""
MCP2CLI tool wrapper: lazy MCP tools via mcp2cli bake mode.

Exposes one lightweight tool per baked config (~100–150 tokens). Execution runs
on demand via subprocess: mcp2cli @<baked_name> <action> --arg=value.
"""

import asyncio
import json
import re
import shutil
from pathlib import Path
from typing import Any

from loguru import logger

from nanoiqqi.agent.tools.base import Tool

# Safe pattern for baked_name: alphanumeric, hyphen, underscore only (no shell metacharacters)
BAKED_NAME_PATTERN = re.compile(r"^[a-zA-Z0-9_-]+$")


def _validate_baked_name(name: str) -> bool:
    """Return True if name is safe for shell usage (no injection)."""
    return bool(name and BAKED_NAME_PATTERN.match(name))


def _build_mcp2cli_args(baked_name: str, action: str, args: dict[str, Any] | None) -> list[str]:
    """Build argv for mcp2cli: mcp2cli @<baked_name> <action> [--k=v ...]."""
    cmd = ["mcp2cli", f"@{baked_name}", action]
    if args:
        for k, v in args.items():
            if v is None:
                continue
            if isinstance(v, (dict, list)):
                cmd.append(f"--{k}={json.dumps(v)}")
            else:
                cmd.append(f"--{k}={v}")
    return cmd


class MCP2CLITool(Tool):
    """
    Tool that delegates to mcp2cli baked configs.

    Presents a minimal schema to the LLM (action + generic args). Real execution
    is done via subprocess to mcp2cli on first use (lazy).
    """

    def __init__(
        self,
        baked_name: str,
        description: str,
        workspace_path: Path | str,
        timeout_seconds: int = 30,
        skill_md: str | None = None,
    ) -> None:
        """
        Args:
            baked_name: Name of the mcp2cli baked config (e.g. filesystem-readonly).
            description: Short description for the LLM (~80–120 tokens).
            workspace_path: Workspace path (for logging / future use).
            timeout_seconds: Timeout for each mcp2cli invocation.
            skill_md: Optional SKILL.md content to enrich description (not used in schema size).
        """
        if not _validate_baked_name(baked_name):
            raise ValueError(
                f"baked_name must match [a-zA-Z0-9_-]+ (safe for shell), got: {baked_name!r}"
            )
        self._baked_name = baked_name
        self._description = description.strip() or f"Run mcp2cli baked tool @{baked_name}."
        self._workspace_path = Path(workspace_path).expanduser() if workspace_path else Path.cwd()
        self._timeout_seconds = max(1, min(300, timeout_seconds))
        self._skill_md = skill_md

    @property
    def name(self) -> str:
        """Tool name exposed to the LLM (one per baked config)."""
        return f"mcp2cli_{self._baked_name}"

    @property
    def description(self) -> str:
        """Short description to keep context small."""
        return self._description

    @property
    def parameters(self) -> dict[str, Any]:
        """Minimal JSON Schema: action + generic args (no full MCP schema)."""
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "description": "Action to execute (e.g. list_dir, read_file).",
                },
                "args": {
                    "type": "object",
                    "description": "Key-value arguments for the action (e.g. path, path=/foo).",
                    "additionalProperties": True,
                },
            },
            "required": ["action"],
        }

    def to_schema(self) -> dict[str, Any]:
        """OpenAI function schema: minimal footprint for this tool."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }

    async def execute(
        self,
        action: str,
        args: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> str:
        """
        Run mcp2cli @<baked_name> <action> with optional args.

        Returns:
            Stdout on success; error message string on failure (no exception).
        """
        if not action or not isinstance(action, str):
            return "Error: 'action' must be a non-empty string."
        # Merge any extra kwargs into args for flexibility
        merged_args = dict(args) if args else {}
        for k, v in kwargs.items():
            if k != "action" and v is not None:
                merged_args[k] = v

        argv = _build_mcp2cli_args(self._baked_name, action, merged_args or None)
        logger.debug(
            "mcp2cli: executing {} (timeout={}s)",
            " ".join(argv),
            self._timeout_seconds,
        )
        try:
            proc = await asyncio.create_subprocess_exec(
                *argv,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(self._workspace_path),
            )
            try:
                stdout_bytes, stderr_bytes = await asyncio.wait_for(
                    proc.communicate(),
                    timeout=float(self._timeout_seconds),
                )
            except asyncio.TimeoutError:
                proc.kill()
                await proc.wait()
                logger.warning("mcp2cli: timeout after {}s for {}", self._timeout_seconds, argv)
                return f"Error: mcp2cli timed out after {self._timeout_seconds}s."

            stdout = stdout_bytes.decode("utf-8", errors="replace").strip()
            stderr = stderr_bytes.decode("utf-8", errors="replace").strip()
            if proc.returncode != 0:
                msg = stderr or stdout or f"Exit code {proc.returncode}"
                logger.warning("mcp2cli: failed {} -> {}", argv, msg)
                return f"Error: mcp2cli failed: {msg}"

            if stderr:
                logger.debug("mcp2cli stderr: {}", stderr)
            # Try to parse as JSON for structured output; otherwise return raw
            if stdout:
                try:
                    json.loads(stdout)
                    return stdout
                except json.JSONDecodeError:
                    pass
            return stdout or "(no output)"
        except FileNotFoundError:
            logger.error("mcp2cli: binary not found (pip install mcp2cli?)")
            return "Error: mcp2cli not found. Install with: pip install mcp2cli"
        except Exception as e:
            logger.exception("mcp2cli: execute failed for {}", argv)
            return f"Error: {type(e).__name__}: {e}"


def is_mcp2cli_available() -> bool:
    """Return True if mcp2cli is installed and on PATH."""
    return shutil.which("mcp2cli") is not None
