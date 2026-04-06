#!/usr/bin/env bash
# Loads per-project MySQL MCP credentials from .cursor/mcp-mysql.env (gitignored), then starts the server.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="${HERE}/mcp-mysql.env"
if [[ ! -f "${ENV_FILE}" ]]; then
  echo "mvPipeline MySQL MCP: missing ${ENV_FILE}" >&2
  echo "Copy .cursor/mcp-mysql.env.example to mcp-mysql.env and set MYSQL_USER / MYSQL_PASS (and optional MYSQL_* overrides)." >&2
  exit 1
fi
set -a
# shellcheck source=/dev/null
source "${ENV_FILE}"
set +a
exec npx -y mcp-server-mysql@1.0.42
