# WinUI MCP Server

<p align="center">
    <a href="https://pypi.org/project/winui-mcp-server">
        <img src="https://badgen.net/pypi/v/winui-mcp-server?color=yellow" />
    </a>
    <a href="https://pypi.org/project/winui-mcp-server">
    <a href="https://pypistats.org/packages/winui-mcp-server">
        <img src="https://static.pepy.tech/badge/winui-mcp-server" />
    </a>
</p>

> [中文文档](README.cn.md)

An MCP (Model Context Protocol) server that enables AI agents to control **any Windows desktop application** through UI Automation. No screen coordinates needed — controls are located by their class hierarchy and names.

## What It Does

This server exposes 26 tools that let your AI agent:

- **Discover** — explore the UIA tree of any window to find controls
- **Click / Double-click / Right-click / Hover** — interact with controls by name or class
- **Type / Send keys / Hotkeys** — keyboard input to any focused or targeted control
- **Scroll** — scroll up/down on a control or window
- **Read / Set values** — get or set text fields, spinboxes, checkboxes, comboboxes
- **Wait** — wait for a control to appear or disappear (async UI)
- **Window management** — list windows, get window state, focus, restore minimized windows

Every tool returns structured JSON: `{"success": bool, "message": str, "data": dict}`.

## Prerequisites

- **Windows 10/11**
- **Python 3.10+**
- **[uv](https://docs.astral.sh/uv/)** — fast Python package manager (`pip install uv`)

## Setup

### Install uv (if not already installed)

```bash
pip install uv
```

### Install the package

```bash
git clone https://github.com/whyb/winui_mcp_server.git
cd winui_mcp_server

uv sync
```

Or install directly from PyPI (once published):

```bash
uv tool install winui-mcp-server
```

## Install as MCP Server

The server runs via **stdio** transport. Below are configuration instructions for every major agent client.

---

### Claude Code

Add to your project's `.claude/settings.json` or global `~/.claude/settings.json`:

```json
{
  "mcpServers": {
    "winui": {
      "command": "uvx",
      "args": ["winui-mcp-server"]
    }
  }
}
```

Restart Claude Code. The `winui` tools will appear in your tool list.

---

### Codex (OpenAI)

In your Codex project, create or edit `.codex/config.json`:

```json
{
  "mcp_servers": {
    "winui": {
      "command": "uvx",
      "args": ["winui-mcp-server"]
    }
  }
}
```

Restart Codex to pick up the new server.

---

### Cline (VS Code Extension)

1. Open VS Code with the Cline extension installed.
2. Open Cline's MCP settings (gear icon in the Cline panel).
3. Add a new MCP server with the following configuration:

```json
{
  "mcpServers": {
    "winui": {
      "command": "uvx",
      "args": ["winui-mcp-server"],
      "disabled": false
    }
  }
}
```

Alternatively, edit the Cline MCP settings file directly at:
- **Windows**: `%APPDATA%/Code/User/globalStorage/saoudrizwan.claude-dev/settings/cline_mcp_settings.json`
- **macOS**: `~/Library/Application Support/Code/User/globalStorage/saoudrizwan.claude-dev/settings/cline_mcp_settings.json`

---

### OpenCode

Edit `~/.opencode/config.json`:

```json
{
  "mcpServers": {
    "winui": {
      "command": "uvx",
      "args": ["winui-mcp-server"]
    }
  }
}
```

---

### Trae (ByteDance)

1. Open Trae IDE.
2. Go to **Settings > MCP Servers**.
3. Add a new server with:

```json
{
  "winui": {
    "command": "uvx",
    "args": ["winui-mcp-server"]
  }
}
```

Or edit the Trae MCP config file directly (location varies by OS, typically under the Trae user data directory).

---

### Antigravity

Edit your Antigravity MCP configuration file:

```json
{
  "mcpServers": {
    "winui": {
      "command": "uvx",
      "args": ["winui-mcp-server"]
    }
  }
}
```

---

### GitHub Copilot (VS Code)

GitHub Copilot supports MCP in agent mode. Add to your VS Code `settings.json`:

```json
{
  "github.copilot.chat.mcp.servers": {
    "winui": {
      "command": "uvx",
      "args": ["winui-mcp-server"]
    }
  }
}
```

Or use the VS Code settings UI: search for `github.copilot.chat.mcp.servers` and add the server entry.

> **Note:** MCP support in GitHub Copilot requires VS Code 1.99+ and Copilot Chat in agent mode.

---

### Qoder

Edit your Qoder MCP settings:

```json
{
  "mcpServers": {
    "winui": {
      "command": "uvx",
      "args": ["winui-mcp-server"]
    }
  }
}
```

---

### CodeBuddy

Edit your CodeBuddy MCP configuration:

```json
{
  "mcpServers": {
    "winui": {
      "command": "uvx",
      "args": ["winui-mcp-server"]
    }
  }
}
```

---

### Cursor

Edit `.cursor/mcp.json` in your project or `~/.cursor/mcp.json` globally:

```json
{
  "mcpServers": {
    "winui": {
      "command": "uvx",
      "args": ["winui-mcp-server"]
    }
  }
}
```

---

### Windsurf

Edit `~/.codeium/windsurf/mcp_config.json`:

```json
{
  "mcpServers": {
    "winui": {
      "command": "uvx",
      "args": ["winui-mcp-server"]
    }
  }
}
```

---

### Any MCP Client (Generic)

This server uses **stdio** transport and follows the standard MCP protocol. For any client that supports MCP:

| Property | Value |
|----------|-------|
| Transport | `stdio` |
| Command | `uvx` |
| Args | `["winui-mcp-server"]` |
| Server name | `winui` |

## Available Tools (26)

| Category | Tool | Description |
|----------|------|-------------|
| **Window** | `list_windows` | List all top-level windows on the desktop |
| | `get_window_state` | Get window position, size, minimized state |
| | `focus_window` | Bring a window to the foreground |
| **Discovery** | `discover` | Explore the UIA tree (summary view, default depth 2) |
| | `describe` | List direct children with class, name, patterns |
| | `dump_tree` | Full UIA tree dump with detailed info (default depth 4) |
| | `get_control_rect` | Get bounding rectangle of a control |
| | `find_control` | Find controls by name/class without clicking (read-only) |
| **Mouse** | `click` | Click a control by name or class |
| | `double_click` | Double-click a control |
| | `right_click` | Right-click a control |
| | `hover` | Move mouse to a control |
| **Scroll** | `scroll_up` | Scroll up on a control or window |
| | `scroll_down` | Scroll down on a control or window |
| **Keyboard** | `send_key` | Send a single key press |
| | `send_hotkey` | Send a key combination (e.g. Ctrl+c) |
| | `long_press_key` | Hold a key for a duration |
| | `type_text` | Type text into a control |
| **Value** | `get_value` | Read value of an edit/spinbox (ValuePattern) |
| | `get_text` | Read Name text of a control (labels, buttons) |
| | `set_value` | Set value of an edit/spinbox |
| | `toggle` | Toggle a checkbox/switch (force on/off or flip) |
| | `combo_select` | Select an item from a combobox |
| **Wait** | `wait_for` | Wait for a control to appear or disappear |

### Tool Notes

- **`get_value` vs `get_text`**: `get_value` reads from input fields / spinboxes that support ValuePattern. `get_text` reads the Name property of any control (labels, buttons, headers). Use `get_text` for static text, `get_value` for editable fields.

- **`discover` vs `dump_tree`**: `discover` shows a summary (class, name, type) at shallow depth — good for quick exploration. `dump_tree` goes deeper and includes rect, patterns, and visibility info — use when you need the full picture.

- **`toggle`**: Pass `enable=true` to force checked, `enable=false` to force unchecked. Omit `enable` to flip the current state.

- **`find_control` vs `click`**: `find_control` searches and returns info without clicking. Use it to check if a control exists or inspect multiple matches before deciding which to interact with.

- **`wait_for`**: Polls until a control appears or disappears. Useful for loading screens, async dialogs, or waiting for a spinner to go away. Default timeout is 10 seconds.

- **`type_text`**: If you specify a `name` or `control_class`, it types into that control. If you omit both, it types into whatever is currently focused.

## Usage Examples

### With an AI Agent (natural language)

After installing the MCP server, just ask your agent:

- "List all open windows on my desktop"
- "Click the Save button in Notepad"
- "Type 'Hello World' into the search box in my app"
- "Toggle the Dark Mode checkbox in Settings"
- "Wait for the loading spinner to disappear"
- "Read the text of the status label"

### CLI (direct usage)

```bash
# List all windows
uv run python cli_gateway.py list-windows

# Explore Notepad's UI
uv run python cli_gateway.py --window "Notepad" describe
uv run python cli_gateway.py --window "Notepad" dump-tree --depth 3

# Find controls without clicking
uv run python cli_gateway.py --window "Notepad" find --name "Save"

# Interact
uv run python cli_gateway.py --window "Notepad" click --name "Save"
uv run python cli_gateway.py --window "Notepad" type --text "Hello World"
uv run python cli_gateway.py --window "Notepad" hotkey --keys "Ctrl+s"

# Read text from a label
uv run python cli_gateway.py --window "Notepad" get-text --name "Status"

# Wait for a control
uv run python cli_gateway.py --window "MyApp" wait-for --name "Loading" --timeout 15 --disappear

# Focus a window
uv run python cli_gateway.py --window "Notepad" focus

# Launch Accessibility Insights for visual inspection
uv run python cli_gateway.py inspect
```

### Python Script (multi-step workflows)

```python
from driver import AppDriver
import skills_library as sk

driver = AppDriver(window_title="Notepad")

# Discover controls
tree = sk.discover_ui(driver, max_depth=3)

# Find without clicking
result = sk.find_control(driver, name="Save")

# Click and type
sk.click_by_name(driver, "Edit")
sk.type_in(driver, "Hello from Python!")
sk.send_hotkey(driver, "Ctrl+s")

# Wait for confirmation dialog
sk.wait_for_control(driver, name="Save As", timeout=5)
```

## Architecture

```
mcp_server.py          MCP server — exposes all skills as MCP tools (with driver cache)
cli_gateway.py         CLI interface — single-command automation
driver.py              Core UIA engine — window binding, element resolution, driver cache
skills_library.py      Skill primitives — click, type, scroll, toggle, wait, find, etc.
config.py              Project constants
pyproject.toml         Package metadata (pip/uv install support)
```

## License

MIT
