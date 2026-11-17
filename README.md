# WinUI MCP Server

<p align="center">
  <a href="https://pypi.org/project/winui-mcp-server">
    <img src="https://badgen.net/pypi/v/winui-mcp-server?color=yellow" alt="PyPI version">
  </a>
  <a href="https://pypistats.org/packages/winui-mcp-server">
    <img src="https://static.pepy.tech/badge/winui-mcp-server" alt="PyPI downloads">
  </a>
</p>

> [中文文档](README.cn.md)

WinUI MCP Server gives AI agents semantic control of Windows desktop applications
through the Model Context Protocol. It is designed for **Codex, Claude Code,
OpenCode, Cline, GitHub Copilot, Kimi Code, DeepSeek Harness**, and any other MCP
client that supports stdio tools.

The server uses UI Automation first and bundles local PP-OCRv6 models as a
fallback when accessible labels are missing. It works with built-in apps, UWP
apps, Win32 apps, Chromium browsers, and Electron applications such as VS Code.

## Agent-first design

The 0.4 release is optimized around agent reliability rather than raw UIA calls:

- **Stable window ids** from `list_windows` and `launch_app` remove ambiguity when
  several processes or windows share a title.
- **Snapshot-scoped element ids** replace brittle tree paths for normal actions.
- **Compact snapshots** expose actionable controls, text, values, patterns, and
  visibility without forcing an agent to recurse through a large raw tree.
- **Application profiles** provide path-free launch discovery and workflow hints
  for Notepad, Calculator, Paint, Settings, Explorer, VS Code, Edge, Chrome, and
  Media Player.
- **Portable discovery** uses `PATH`, Windows `App Paths`, and registered URI
  protocols. The repository contains no machine-specific install paths.
- **Structured MCP results** include `success`, `message`, `data`, optional
  `verified`, and machine-readable `error` metadata.
- **Batch actions** reduce round trips with `run_actions` while preserving a final
  observation.
- **Real integration tests** run a fresh MCP stdio process for every test, so
  development changes reload the same way a real client does.

## Requirements

- Windows 10 or Windows 11
- Python 3.10+
- [uv](https://docs.astral.sh/uv/)
- Network access only for installation; OCR and automation run locally

## Install

Install as a standalone MCP server tool:

```bash
uv tool install winui-mcp-server
```

Or run directly without a persistent tool install:

```bash
uvx winui-mcp-server
```

For development from a checkout:

```bash
git clone https://github.com/whyb/winui_mcp_server.git
cd winui_mcp_server
uv sync --extra dev
```

## Configure an MCP client

The transport is standard MCP stdio:

```text
command: uvx
args:    ["winui-mcp-server"]
```

Common configurations:

### Codex

```toml
[mcp_servers.winui]
command = "uvx"
args = ["winui-mcp-server"]
```

### Claude Code

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

### OpenCode V2

```jsonc
{
  "$schema": "https://opencode.ai/config.json",
  "mcp": {
    "servers": {
      "winui": {
        "type": "local",
        "command": ["uvx", "winui-mcp-server"]
      }
    }
  }
}
```

### VS Code / GitHub Copilot

```json
{
  "servers": {
    "winui": {
      "type": "stdio",
      "command": "uvx",
      "args": ["winui-mcp-server"]
    }
  }
}
```

See [docs/CLIENTS.md](docs/CLIENTS.md) for Cline, local development, and generic
client guidance.

## Recommended agent loop

1. `launch_app` for a supported app, or `list_windows` for an existing app.
   `arguments` accepts a path/URL/deep-link string or an argument list for
   flags such as `--new-window` and `--user-data-dir`.
2. Use the returned `window_id`.
3. Call `snapshot`. Use `query` to narrow large UI trees.
4. Act with `element_id` from the latest snapshot.
5. Verify with another snapshot, `get_value`, `get_text`, or `wait_for`.
6. Re-snapshot after navigation or any UI change.

The server sends this workflow through MCP initialization instructions. It is
also exposed as the `winui://guide` resource, the `automate_windows_task` prompt,
and the portable [WinUI automation skill](skills/winui-automation/SKILL.md).

Read the full [agent guide](docs/AGENT_GUIDE.md).

## Example agent requests

- "Launch Notepad with a new temporary file, type a short note, and verify it."
- "Open Settings to the display page and describe the available controls."
- "In Edge, open a URL and click the sign-in button without using coordinates."
- "Find the Save command in VS Code and report whether it is enabled."
- "Open Calculator, calculate 19 × 23, and read the result."
- "Inspect every open Explorer window and choose the one matching a folder name."
- "OCR-fallback this app's toolbar because its buttons have no accessible names."

## Tool surface

| Category | Tools |
|---|---|
| Applications | `list_apps`, `launch_app` |
| Windows | `list_windows`, `get_window_state`, `focus_window`, `window_action`, `move_window`, `reset_driver` |
| Observation | `snapshot`, `ocr_scan`, `find_control`, `wait_for` |
| Legacy discovery | `discover`, `describe`, `dump_tree`, `get_control_rect` |
| Mouse | `click`, `double_click`, `right_click`, `hover`, `drag_control` |
| Scrolling | `scroll_up`, `scroll_down` |
| Keyboard | `send_key`, `send_hotkey`, `long_press_key`, `type_text` |
| Values | `get_value`, `get_text`, `set_value`, `toggle`, `combo_select` |
| Workflow | `run_actions` |

### Stable element ids

A snapshot returns compact elements such as:

```json
{
  "element_id": "e42",
  "role": "Button",
  "name": "Save",
  "text": "Save",
  "auto_id": "saveButton",
  "interactive": true,
  "enabled": true,
  "patterns": ["Invoke"]
}
```

Pass `e42` to `click` or `run_actions`. If the UI changes, the old id becomes
stale and the server asks for a new snapshot rather than silently clicking the
wrong control.

## Result contract

```json
{
  "success": true,
  "message": "Value set and verified",
  "data": {},
  "verified": true
}
```

Failures include:

```json
{
  "success": false,
  "message": "Element id is stale",
  "data": {},
  "error": {
    "code": "operation_failed",
    "retryable": false,
    "hint": "Call snapshot again before acting."
  }
}
```

MCP clients receive both readable text content and structured tool content.

## OCR fallback

When accessible text is missing:

```text
snapshot(window_id="0x1234", include_ocr=true, query="Save")
```

The bundled PP-OCRv6 tiny detector and recognizer run locally through ONNX
Runtime. OCR text is spatially bound to the smallest containing UIA control. No
image or text is sent to an external OCR service.

## CLI

The same engine is available without an MCP client:

```powershell
# Discover applications and windows
uv run python cli_gateway.py list-apps
uv run python cli_gateway.py list-windows

# Launch and inspect
uv run python cli_gateway.py launch-app --app notepad
uv run python cli_gateway.py --window-id 0x1234 snapshot --query save

# Act and verify
uv run python cli_gateway.py --window-id 0x1234 click --element-id e8
uv run python cli_gateway.py --window-id 0x1234 get-value --element-id e12
```

Run `uv run python cli_gateway.py --help` for the complete command list.

## Python API

```python
from winui_mcp.driver import AppDriver
from winui_mcp import skills_library as sk

driver = AppDriver(window_id="0x1234")
snapshot = sk.snapshot(driver, query="Save", interactive_only=True)
element = snapshot["data"]["elements"][0]

assert sk.activate_reference(
    driver, "click", element_id=element["element_id"]
)["success"]
```

## Testing

Unit tests are safe and do not control the desktop:

```bash
uv run --extra dev python -m pytest tests -q
```

Live protocol and application tests are opt-in:

```powershell
$env:WINUI_RUN_INTEGRATION="1"
uv run --extra dev python -m pytest tests/integration/test_mcp_stdio.py -q

$env:WINUI_RUN_APP_LAUNCH="1"
uv run --extra dev python -m pytest tests/integration/test_app_launch_matrix.py -q

$env:WINUI_RUN_APP_INTERACTION="1"
uv run --extra dev python -m pytest tests/integration/test_app_interactions.py tests/integration/test_calculator_interaction.py -q
```

See [docs/TESTING.md](docs/TESTING.md) for the matrix, environment gates, local
Conda workflow, and release checks.

## Architecture

```text
winui_mcp/
  mcp_server.py       Structured MCP tool surface and server instructions
  skills_library.py   Snapshot, reference actions, OCR, and workflow primitives
  driver.py           Window binding, Win32 discovery, UIA traversal, refs
  apps.py             Portable common-app catalog and launcher
  capture.py          GDI window capture
  ocr.py              PP-OCRv6 ONNX detector/recognizer
  ocr_pipeline.py     Spatial binding of OCR lines to UIA controls
  config.py           Bundled resource discovery
  models/PP-OCRv6/    Local OCR models and vocabularies
```

## Safety and limitations

- UI Automation quality depends on the target application's accessibility
  provider. OCR is available as a fallback, but it is inherently approximate.
- Browsers and Electron apps may expose large or lazy trees. Use `query`,
  `interactive_only`, and bounded `max_nodes`.
- Coordinate-based operation is not exposed as the preferred workflow.
- Destructive, financial, messaging, and security-sensitive actions require
  explicit user intent.
- Some elevated applications cannot be automated from a non-elevated process.

## License

MIT
