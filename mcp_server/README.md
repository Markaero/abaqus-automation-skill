# Abaqus MCP Server

Lets any MCP-capable agent (Claude Desktop, Claude Code, Cursor, Codex, …)
work with Abaqus through tools instead of reading instructions.

The server runs in **ordinary Python 3.10+** on the machine where Abaqus
is installed. It cannot run inside Abaqus's own Python; later steps call
Abaqus through `abaqus cae noGUI`.

## Status

| Step | Tools | Needs Abaqus |
|------|-------|--------------|
| **1 (done)** | `abaqus_api_areas`, `abaqus_api_list_area`, `abaqus_api_search`, `abaqus_api_lookup` — offline API documentation | No |
| 2 | `inspect_model` via `abaqus cae noGUI` | Yes |
| 3 | Result reading (IR, field max, history) | Yes |
| 4 | Write tools (loads, masses, couplings…) with dry-run, backup, diff | Yes |
| 5 | `run_script` fallback for any API | Yes |

## Setup (Windows, once)

```powershell
cd D:\tools\abaqus-automation                      # the kit folder
py -3.11 -m venv .venv                             # any Python 3.10+
.venv\Scripts\pip install -r mcp_server\requirements.txt
.venv\Scripts\pip install --no-deps --target .abqpy "abqpy==2024.*"   # match your Abaqus version
.venv\Scripts\python tools\api_lookup.py --areas   # quick check: prints the API areas
```

## Connect your agent

Use the absolute paths of the venv's `python.exe` and of `server.py`.

**Claude Code**

```powershell
claude mcp add abaqus -- D:\tools\abaqus-automation\.venv\Scripts\python.exe D:\tools\abaqus-automation\mcp_server\server.py
```

**Claude Desktop** — `%APPDATA%\Claude\claude_desktop_config.json`
**Cursor** — `.cursor\mcp.json` in the project (or the global one)

```json
{
  "mcpServers": {
    "abaqus": {
      "command": "D:\\tools\\abaqus-automation\\.venv\\Scripts\\python.exe",
      "args": ["D:\\tools\\abaqus-automation\\mcp_server\\server.py"]
    }
  }
}
```

**Codex** — `~/.codex/config.toml`

```toml
[mcp_servers.abaqus]
command = 'D:\tools\abaqus-automation\.venv\Scripts\python.exe'
args = ['D:\tools\abaqus-automation\mcp_server\server.py']
```

Restart the client, then ask something like *"How do I define
surface-to-surface contact in Abaqus? Use the abaqus tools."* — the agent
should call `abaqus_api_search` / `abaqus_api_lookup`.

## Test

```powershell
.venv\Scripts\python -m unittest tests.test_mcp_server -v
```

Starts the server over stdio exactly like a client does, lists the tools
and calls each one.
