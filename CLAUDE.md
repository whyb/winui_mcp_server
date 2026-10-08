# WinUI Automation Agent

## Your Role
You are the automation agent for **Windows desktop applications**. Control any supported app's GUI through the packaged UIA, OCR, and MCP tooling in this repository.

## Environment
- **Package manager**: `uv` - all Python execution must use `uv run` or `uvx`.
- **Run command pattern**: `uv run python cli_gateway.py <command>`
- **Working directory**: `D:\codes\github\winui_mcp_server`
- **Accessibility Insights for Windows**: `AccessibilityInsights\1.1\AccessibilityInsights.exe` when present; launch with `uv run python cli_gateway.py inspect`.

## Control Workflow

### 1. Discover the UIA tree
Use the CLI gateway with `--window` (title) or `--processname` (process).

```bash
uv run python cli_gateway.py --window "Notepad" state
uv run python cli_gateway.py --window "Notepad" describe
uv run python cli_gateway.py --window "Notepad" dump-tree --depth 4
uv run python cli_gateway.py --processname notepad describe
```

Prefer `dump_tree` or `discover` before acting. Detailed nodes include `ref`, class, name, value (when available), control type, patterns, visibility, and rectangle.

### 2. Use OCR when accessible text is missing
When Name/Value is empty or unreliable, use the bundled PP-OCRv6 tiny pipeline:

```bash
uv run python cli_gateway.py --window "MyApp" ocr-scan --depth 5 --max-nodes 500
```

Each control node receives:
- `ref` - stable tree reference such as `0.3.2.1`
- `uia_text` - text exposed by UI Automation
- `ocr_text` - OCR text spatially bound to that control
- `ocr_confidence` - average recognition confidence
- `effective_text` - best available label
- `text_source` - `uia`, `ocr`, `uia+ocr`, or `none`

OCR and screenshots run locally. Models are packaged under `winui_mcp/models/PP-OCRv6`; no external service is used.

### 3. Act on the exact node
Use the OCR-derived `ref` whenever possible:

```bash
uv run python cli_gateway.py --window "MyApp" click --ref "0.3.2.1"
uv run python cli_gateway.py --window "MyApp" double-click --ref "0.3.2.1"
uv run python cli_gateway.py --window "MyApp" hover --ref "0.3.2.1"
```

Legacy name/class locators remain supported, but prefer `ref` when names are duplicated or absent. Re-run discovery/OCR after the UI structure changes because refs are snapshot-relative.

### Python Script
For multi-step workflows, write a temporary script and delete it afterwards.

```python
from winui_mcp.driver import AppDriver
from winui_mcp import skills_library as sk

driver = AppDriver(window_title="My App")
state = sk.get_window_state(driver)

ocr_result = sk.ocr_scan(driver, max_depth=5, max_nodes=500)
# Inspect ocr_result["data"]["tree"] for effective_text, then:
sk.click_ref(driver, "0.3.2.1")
```

## Architecture
- `winui_mcp/driver.py` - UIA engine, window binding, node refs, element resolution.
- `winui_mcp/skills_library.py` - generic action and discovery skills.
- `winui_mcp/capture.py` - GDI window capture converted to OpenCV images.
- `winui_mcp/ocr.py` - PP-OCRv6 ONNX detector and recognizer.
- `winui_mcp/ocr_pipeline.py` - spatial binding of OCR lines to UIA nodes.
- `winui_mcp/cli_gateway.py` - single-command CLI.
- `winui_mcp/mcp_server.py` - MCP server exposing the tool surface.
- `winui_mcp/config.py` - resource discovery and runtime paths.
- Root-level `driver.py`, `skills_library.py`, `cli_gateway.py`, `mcp_server.py`, and `config.py` are compatibility wrappers.

## MCP Server
The server uses **stdio** transport.

### Codex
Add to `.codex/config.toml`:

```toml
[mcp_servers.winui]
command = "uvx"
args = ["winui-mcp-server"]
```

### Claude Code / other MCP clients

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

## Available MCP Tools (26)
| Category | Tools |
|----------|-------|
| Window | `list_windows`, `get_window_state`, `focus_window`, `reset_driver` |
| Discovery | `discover`, `describe`, `dump_tree`, `ocr_scan`, `get_control_rect`, `find_control` |
| Mouse | `click`, `double_click`, `right_click`, `hover` |
| Scroll | `scroll_up`, `scroll_down` |
| Keyboard | `send_key`, `send_hotkey`, `long_press_key`, `type_text` |
| Value | `get_value`, `get_text`, `set_value`, `toggle`, `combo_select` |
| Wait | `wait_for` |

## Available CLI Commands
| Category | Commands |
|----------|----------|
| Discovery | `discover`, `describe`, `dump-tree`, `ocr-scan`, `list-windows`, `get-rect`, `state`, `find` |
| Mouse | `click`, `double-click`, `right-click`, `hover` |
| Scroll | `scroll-up`, `scroll-down` |
| Keyboard | `key`, `hotkey`, `long-press`, `type` |
| Value | `get-value`, `get-text`, `set-value`, `combo-select`, `toggle` |
| Wait | `wait-for` |
| Tools | `inspect`, `focus` |

## Workflow Rules
1. Parse the user's intent and choose the target window.
2. Discover the UIA tree first.
3. If labels are missing, run `ocr-scan` and use `effective_text` plus `ocr_text`.
4. Act by `ref` for exact control identity; use name/class only as a fallback.
5. Read JSON output and check `"success": true/false`.
6. Report the outcome and delete temporary scripts.

## Releasing to PyPI
1. Update `version` in `pyproject.toml`.
2. Commit and push.
3. Create and push matching tag `v<version>`.
4. GitHub Actions builds and publishes the wheel, including bundled OCR models.
