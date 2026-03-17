# Notion + mcp2cli + nanoiqqi (Docker → local)

This guide sets up **Notion MCP** through **mcp2cli bake mode** so nanoiqqi registers only a **minimal schema** (action + args) and executes on demand.

## Option A (recommended): Local Notion MCP server in Docker (STDIO)

### 1) Create a Notion integration token

Create an internal integration and copy the token (`ntn_...`) from:

`https://www.notion.so/profile/integrations`

Share the relevant pages/databases with the integration.

### 2) Install mcp2cli (in the repo venv)

```bash
cd /home/ultrita/iqqi-nanobot
python3 -m venv .venv
. .venv/bin/activate
pip install -e ".[dev]"
pip install mcp2cli
```

### 3) Bake the tool (no secrets stored)

```bash
export NOTION_TOKEN="ntn_..."
./scripts/bake_notion_mcp2cli.sh
```

Verify:

```bash
/home/ultrita/iqqi-nanobot/.venv/bin/mcp2cli @notion --list
```

### 4) Enable in nanoiqqi

Merge into `~/.nanoiqqi/config.json`:

```json
{
  "tools": {
    "mcp2cli": {
      "enabled": true,
      "bakedTools": ["notion"],
      "timeoutSeconds": 30
    }
  }
}
```

Start:

```bash
nanoiqqi agent --logs
```

In chat, call the tool as:
- tool: `mcp2cli_notion`
- args: `{"action":"search","args":{"query":"Roadmap"}}`

## Option B: Remote Notion MCP (HTTP/SSE)

If you have a hosted Notion MCP URL, you can bake it with:

```bash
mcp2cli bake create notion-remote \
  --mcp "https://<notion-mcp-url>" \
  --transport auto \
  --oauth \
  --include "search*,retrieve*,list*,query*,create*,update*,append*,comment*" \
  --cache-ttl 3600

mcp2cli @notion-remote --list
```

Then set `bakedTools` to `["notion-remote"]`.

## Notes

- `mcp2cli` is the MCP **client**. The Notion MCP server can be local (Docker/STDIO) or remote (HTTP/SSE).
- With `tools.mcp2cli`, nanoiqqi never imports full MCP tool schemas into the LLM context.

