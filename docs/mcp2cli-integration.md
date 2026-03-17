# mcp2cli integration

nanoiqqi can use **mcp2cli** (bake mode) to register MCP tools with a **minimal token footprint** (~100–150 tokens per tool instead of 2000–5000 for full MCP schemas). Execution runs on demand via `mcp2cli @<baked_name> <action> --arg=value`.

## Requirements

- **mcp2cli** must be installed and on `PATH` (external dependency, not bundled):
  ```bash
  pip install mcp2cli
  ```
- Baked configs must be created beforehand with `mcp2cli bake create ...`.

## Configuration

In `~/.nanoiqqi/config.json` add (or merge into existing `tools`):

```json
{
  "tools": {
    "mcp2cli": {
      "enabled": true,
      "bakedTools": ["filesystem-readonly", "github-readonly"],
      "timeoutSeconds": 30,
      "cacheDir": "~/.nanoiqqi/.mcp2cli-cache"
    },
    "mcpServers": { ... }
  }
}
```

| Field | Description |
|-------|-------------|
| `enabled` | If `true`, one lightweight tool per `bakedTools` entry is registered. |
| `bakedTools` | List of baked config names (e.g. `filesystem-readonly`). |
| `timeoutSeconds` | Timeout per mcp2cli invocation (1–300). Default: 30. |
| `cacheDir` | Optional cache directory for mcp2cli. |

**Note:** If `mcp2cli` is not installed, the agent still starts; a warning is logged and no mcp2cli tools are registered.

## Creating baked configs (bake)

Create baked tools **before** enabling them in config.

### Example: filesystem read-only

```bash
mcp2cli bake create filesystem-readonly \
  --mcp-stdio "npx -y @modelcontextprotocol/server-filesystem /home/user/docs" \
  --include "read_*,list_*,search_*" \
  --exclude "write_*,delete_*,move_*" \
  --cache-ttl 3600
```

### List / inspect baked configs

```bash
mcp2cli bake list
```

### Run a tool manually (for testing)

```bash
mcp2cli @filesystem-readonly list_dir --path=/home/user/docs
```

## Behaviour in nanoiqqi

1. **Startup:** When `mcp2cli.enabled` is `true` and the `mcp2cli` binary is found, one `MCP2CLITool` per `bakedTools` entry is registered (e.g. `mcp2cli_filesystem-readonly`).
2. **Schema:** The LLM sees a minimal function: `action` (string) and `args` (object). No full MCP schema is sent.
3. **Execution:** When the LLM calls the tool, nanoiqqi runs:
   `mcp2cli @<baked_name> <action> [--k=v ...]`
   and returns stdout (or an error message on timeout / non-zero exit).
4. **Compatibility:** Existing `mcpServers` are unchanged; you can use both MCP servers and mcp2cli baked tools.

## Token savings

- **Before (full MCP):** ~2000–5000 tokens for all MCP tool schemas at startup.
- **After (mcp2cli):** ~100–150 tokens per baked tool.
- **Result:** ~95%+ reduction in context used for tool definitions when using several MCP capabilities.

## Troubleshooting

| Issue | What to do |
|-------|------------|
| Agent starts but no mcp2cli tools | Ensure `pip install mcp2cli` and `mcp2cli bake list` shows your baked config. Check logs for `mcp2cli: enabled but binary not found`. |
| Tool returns "mcp2cli not found" | Install mcp2cli in the same environment that runs nanoiqqi (or ensure it’s on `PATH`). |
| Timeout errors | Increase `timeoutSeconds` in config or simplify the action. |
| Invalid baked name | Use only `[a-zA-Z0-9_-]` in baked config names (e.g. `filesystem-readonly`, not `my tool`). |
| Wrong or empty output | Run the same command manually: `mcp2cli @<baked_name> <action> --arg=value` and fix the bake or args. |

## Optional: SKILL.md per baked tool

You can place a `SKILL.md` (with optional YAML frontmatter) under `~/.nanoiqqi/skills/<baked_name>/` to provide richer descriptions or examples. The wrapper supports a `skill_md` constructor argument for future use; the current default description is generic and stays small for token savings.
