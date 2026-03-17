#!/usr/bin/env bash
set -euo pipefail

# Bake a Notion MCP tool for nanoiqqi via mcp2cli, running the MCP server in Docker (STDIO).
#
# Requirements:
#   - docker
#   - mcp2cli available (recommended: /home/ultrita/iqqi-nanobot/.venv/bin/mcp2cli)
#   - NOTION_TOKEN in environment (ntn_...)
#
# This script does NOT write secrets into baked config. It forwards NOTION_TOKEN via env: indirection.
#
# Usage:
#   export NOTION_TOKEN="ntn_...."
#   ./scripts/bake_notion_mcp2cli.sh

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MCP2CLI="${MCP2CLI:-"$ROOT_DIR/.venv/bin/mcp2cli"}"
BAKED_NAME="${BAKED_NAME:-notion}"

if ! command -v docker >/dev/null 2>&1; then
  echo "Error: docker not found in PATH" >&2
  exit 1
fi

if [[ ! -x "$MCP2CLI" ]]; then
  echo "Error: mcp2cli not found at '$MCP2CLI'." >&2
  echo "Install it in the repo venv: $ROOT_DIR/.venv/bin/pip install mcp2cli" >&2
  exit 1
fi

if [[ -z "${NOTION_TOKEN:-}" ]]; then
  echo "Error: NOTION_TOKEN is not set." >&2
  echo "Set it first: export NOTION_TOKEN=\"ntn_...\"" >&2
  exit 1
fi

echo "Baking '$BAKED_NAME' using Docker image mcp/notion (STDIO)..."

"$MCP2CLI" bake create "$BAKED_NAME" \
  --mcp-stdio "docker run --rm -i -e NOTION_TOKEN mcp/notion" \
  --env "NOTION_TOKEN=env:NOTION_TOKEN" \
  --include "search*,retrieve*,list*,query*,create*,update*,append*,comment*" \
  --cache-ttl 3600

echo
echo "OK. Verify:"
echo "  $MCP2CLI @$BAKED_NAME --list"
echo
echo "Then enable in ~/.nanoiqqi/config.json (merge into tools):"
cat <<EOF
{
  "tools": {
    "mcp2cli": {
      "enabled": true,
      "bakedTools": ["$BAKED_NAME"],
      "timeoutSeconds": 30
    }
  }
}
EOF

