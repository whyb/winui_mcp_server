# WinUI Automation Agent

## Role

You are the development and automation agent for **Windows desktop applications**.
Use the repository's UI Automation, local OCR, CLI, and MCP tools. Keep behavior
portable across Windows 10/11 machines and across MCP clients such as Codex,
Claude Code, OpenCode, Cline, Copilot, Kimi Code, and DeepSeek Harness.

## Environment

- Published users and CI use `uv`: `uv sync --extra dev`, `uv run`, and `uvx`.
- Local development may use a Conda environment named `winui_mcp_server` to avoid
  rebuilding the package on every iteration.
- Never commit machine-specific installation paths, user directories, credentials,
  screenshots, OCR captures, or copied application install locations.
- Resolve repository resources with relative paths or `pathlib.Path(__file__)`.
- Accessibility Insights is optional. Discover it through `config.py` or the
  `ACCESSIBILITY_INSIGHTS_PATH` environment variable.

## Agent-first control workflow

1. If the app is not running, call `launch_app` or the `launch-app` CLI command.
   Otherwise call `list_windows` / `list-windows`.
2. Keep the returned `window_id`. Prefer it over window titles or process names,
   especially when a process has several windows.
3. Call `snapshot` with `window_id`. Use `query` for large UIs.
4. Act with the `element_id` from the latest snapshot. Prefer stable ids over
   names, classes, tree refs, or coordinates.
5. Verify with a new snapshot, `get_value`, `get_text`, or `wait_for`.
6. Re-snapshot after navigation, dialogs, mode changes, tab changes, or any other
   visible UI change.

## Tool surface

The MCP server exposes 31 tools:

- Applications: `list_apps`, `launch_app`
- Windows: `list_windows`, `get_window_state`, `focus_window`,
  `window_action`, `reset_driver`
- Observation: `snapshot`, `ocr_scan`, `find_control`, `wait_for`
- Legacy discovery: `discover`, `describe`, `dump_tree`, `get_control_rect`
- Mouse: `click`, `double_click`, `right_click`, `hover`
- Scroll: `scroll_up`, `scroll_down`
- Keyboard: `send_key`, `send_hotkey`, `long_press_key`, `type_text`
- Values: `get_value`, `get_text`, `set_value`, `toggle`, `combo_select`
- Workflow: `run_actions`

The server also publishes initialization instructions, a `winui://guide`
resource, an automation prompt, and the portable
`skills/winui-automation/SKILL.md` skill.

## OCR fallback

Use OCR only when accessible labels are missing or unreliable:

```powershell
uv run python cli_gateway.py --window-id 0x1234 snapshot --ocr --query "Save"
```

OCR models are bundled under `winui_mcp/models/PP-OCRv6` and run locally through
ONNX Runtime. No screenshot or text is sent to an external OCR service.

## Architecture

- `winui_mcp/driver.py`: Win32/UIA window binding, discovery, refs, and actions.
- `winui_mcp/skills_library.py`: snapshots, reference actions, OCR, and workflows.
- `winui_mcp/apps.py`: portable common-app catalog and launcher.
- `winui_mcp/mcp_server.py`: structured MCP tools and server instructions.
- `winui_mcp/cli_gateway.py`: equivalent CLI for diagnostics and development.
- `winui_mcp/capture.py`: GDI capture.
- `winui_mcp/ocr.py` and `ocr_pipeline.py`: OCR and spatial binding.
- `winui_mcp/config.py`: bundled resource discovery.

## MCP configuration

Published users:

```toml
[mcp_servers.winui]
command = "uvx"
args = ["winui-mcp-server"]
```

Local Conda development:

```toml
[mcp_servers.winui]
command = "conda"
args = [
  "run",
  "-n",
  "winui_mcp_server",
  "python",
  "-m",
  "winui_mcp.mcp_server",
]
```

See `docs/CLIENTS.md` for OpenCode, Claude Code, Copilot, Cline, and generic
stdio examples.

## Development rules

- Follow an analyze-test-change-retest loop.
- Run static checks and safe unit tests before and after code changes:
  `uv run --extra dev ruff check winui_mcp tests` and
  `uv run --extra dev python -m pytest tests -q`.
- Add tests for every bug fix or new tool contract.
- Live tests are opt-in:
  - `WINUI_RUN_INTEGRATION=1` for the MCP stdio round trip.
  - `WINUI_RUN_APP_SMOKE=1` for read-only common-app inspection.
  - `WINUI_RUN_APP_LAUNCH=1` for the launch matrix.
- Ensure live tests close only windows they created and never terminate unrelated
  user processes.
- Every MCP tool result should remain structured and machine-readable:
  `success`, `message`, `data`, optional `verified`, and an `error` object on
  failure.
- Keep schemas strictly typed and descriptions action-oriented.
- Prefer exact matching and stable ids; use partial matching only intentionally.
- Delete temporary scripts, logs, generated captures, and debug artifacts.

## Release process

1. Update the version in `pyproject.toml` and `server.json`.
2. Run `uv lock`, unit tests, live integration tests where available, and
   `uv build`.
3. Inspect the built wheel for bundled OCR models and package metadata.
4. Commit and push.
5. Create and push the matching `v<version>` tag.
6. GitHub Actions builds and publishes to PyPI through trusted publishing.
