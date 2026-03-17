"""Unit tests for MCP2CLITool and mcp2cli integration."""

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from nanoiqqi.agent.tools.mcp2cli_wrapper import (
    BAKED_NAME_PATTERN,
    MCP2CLITool,
    _build_mcp2cli_args,
    _validate_baked_name,
    is_mcp2cli_available,
)
from nanoiqqi.agent.tools.registry import ToolRegistry


# --- _validate_baked_name / _build_mcp2cli_args ---


def test_validate_baked_name_allows_safe_names() -> None:
    assert _validate_baked_name("filesystem-readonly") is True
    assert _validate_baked_name("github_readonly") is True
    assert _validate_baked_name("a") is True
    assert _validate_baked_name("a1-B_2") is True


def test_validate_baked_name_rejects_unsafe() -> None:
    assert _validate_baked_name("") is False
    assert _validate_baked_name("foo; rm -rf") is False
    assert _validate_baked_name("foo bar") is False
    assert _validate_baked_name("foo$bar") is False
    assert _validate_baked_name("../etc") is False


def test_build_mcp2cli_args_action_only() -> None:
    assert _build_mcp2cli_args("fs", "list_dir", None) == ["mcp2cli", "@fs", "list_dir"]


def test_build_mcp2cli_args_with_args() -> None:
    argv = _build_mcp2cli_args("fs", "read_file", {"path": "/tmp/x"})
    assert argv == ["mcp2cli", "@fs", "read_file", "--path=/tmp/x"]


def test_build_mcp2cli_args_skips_none_values() -> None:
    argv = _build_mcp2cli_args("fs", "list_dir", {"path": "/x", "optional": None})
    assert "--path=/x" in argv
    assert "optional" not in " ".join(argv)


# --- MCP2CLITool registration and schema ---


def test_mcp2cli_tool_invalid_baked_name_raises() -> None:
    with pytest.raises(ValueError, match="safe for shell"):
        MCP2CLITool(baked_name="bad name", description="x", workspace_path="/tmp")


def test_mcp2cli_tool_schema_minimal() -> None:
    tool = MCP2CLITool(
        baked_name="filesystem-readonly",
        description="Read-only filesystem MCP.",
        workspace_path="/workspace",
    )
    assert tool.name == "mcp2cli_filesystem-readonly"
    assert "Read-only" in tool.description
    schema = tool.to_schema()
    assert schema["type"] == "function"
    assert schema["function"]["name"] == tool.name
    params = schema["function"]["parameters"]
    assert "action" in params["properties"]
    assert "args" in params["properties"]
    assert params["required"] == ["action"]
    # Token footprint: description + params should be small (~100–150 tokens)
    desc_len = len(tool.description) + len(str(params))
    assert desc_len < 800


def test_mcp2cli_tool_registry_definitions() -> None:
    registry = ToolRegistry()
    tool = MCP2CLITool(
        baked_name="test-baked",
        description="Test baked tool.",
        workspace_path="/tmp",
    )
    registry.register(tool)
    defs = registry.get_definitions()
    assert len(defs) == 1
    assert defs[0]["function"]["name"] == "mcp2cli_test-baked"


# --- Execute: success and error handling (mocked subprocess) ---


@pytest.mark.asyncio
async def test_mcp2cli_execute_success_returns_stdout() -> None:
    tool = MCP2CLITool(
        baked_name="fs",
        description="FS tool",
        workspace_path="/tmp",
        timeout_seconds=10,
    )
    fake_proc = MagicMock()
    fake_proc.returncode = 0
    fake_proc.communicate = AsyncMock(return_value=(b'{"files":[]}', b""))
    fake_proc.wait = AsyncMock(return_value=0)

    with patch("asyncio.create_subprocess_exec", new_callable=AsyncMock, return_value=fake_proc):
        result = await tool.execute(action="list_dir", args={"path": "/tmp"})
    assert result == '{"files":[]}'


@pytest.mark.asyncio
async def test_mcp2cli_execute_non_zero_returns_error_message() -> None:
    tool = MCP2CLITool(
        baked_name="fs",
        description="FS tool",
        workspace_path="/tmp",
        timeout_seconds=10,
    )
    fake_proc = MagicMock()
    fake_proc.returncode = 1
    fake_proc.communicate = AsyncMock(return_value=(b"", b"No such path"))
    fake_proc.wait = AsyncMock(return_value=1)

    with patch("asyncio.create_subprocess_exec", new_callable=AsyncMock, return_value=fake_proc):
        result = await tool.execute(action="read_file", args={"path": "/nonexistent"})
    assert "Error" in result
    assert "No such path" in result or "1" in result


@pytest.mark.asyncio
async def test_mcp2cli_execute_timeout_returns_error_message() -> None:
    tool = MCP2CLITool(
        baked_name="fs",
        description="FS tool",
        workspace_path="/tmp",
        timeout_seconds=1,
    )
    fake_proc = MagicMock()
    fake_proc.communicate = AsyncMock(side_effect=asyncio.TimeoutError())
    fake_proc.kill = MagicMock()
    fake_proc.wait = AsyncMock(return_value=0)

    with patch("asyncio.create_subprocess_exec", new_callable=AsyncMock, return_value=fake_proc):
        result = await tool.execute(action="slow_action")
    assert "Error" in result
    assert "timed out" in result


@pytest.mark.asyncio
async def test_mcp2cli_execute_missing_action_returns_validation_message() -> None:
    tool = MCP2CLITool(
        baked_name="fs",
        description="FS tool",
        workspace_path="/tmp",
    )
    result = await tool.execute(action="")
    assert "Error" in result
    assert "action" in result


@pytest.mark.asyncio
async def test_mcp2cli_execute_file_not_found_returns_install_message() -> None:
    tool = MCP2CLITool(
        baked_name="fs",
        description="FS tool",
        workspace_path="/tmp",
    )
    with patch("asyncio.create_subprocess_exec", new_callable=AsyncMock, side_effect=FileNotFoundError()):
        result = await tool.execute(action="list_dir")
    assert "Error" in result
    assert "mcp2cli" in result


# --- is_mcp2cli_available ---


def test_is_mcp2cli_available_mocked() -> None:
    with patch("nanoiqqi.agent.tools.mcp2cli_wrapper.shutil.which") as m:
        m.return_value = "/usr/bin/mcp2cli"
        assert is_mcp2cli_available() is True
        m.return_value = None
        assert is_mcp2cli_available() is False
