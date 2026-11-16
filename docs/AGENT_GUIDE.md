# Agent Automation Guide

This guide is the shortest reliable path for an AI agent using WinUI MCP Server.
It applies to Codex, Claude Code, OpenCode, Cline, Copilot, Kimi Code, DeepSeek
Harness, and any other MCP client that supports stdio tools.

## Use the observe-act-verify loop

1. **Find a target.** Call `launch_app` if the app is not running; otherwise call
   `list_windows`.
2. **Bind deterministically.** Keep the returned `window_id`. Prefer it over
   `window_title` or `process_name`, especially for browsers, Explorer, and VS
   Code where several windows may share one process.
3. **Observe.** Call `snapshot` with `window_id`. Start with
   `interactive_only=true`; use `query` when the tree is large.
4. **Act by `element_id`.** Pass the id from the latest snapshot to `click`,
   `type_text`, `set_value`, `toggle`, `combo_select`, or another action tool.
5. **Verify.** Call `snapshot`, `get_value`, `get_text`, or `wait_for`. A click
   response with `verified=false` means the input was sent, not that the desired
   state was reached.
6. **Re-observe after UI changes.** Navigation, dialogs, mode changes, browser
   page changes, and panel switches invalidate old element ids.

## Snapshot contract

A successful snapshot returns:

- `window`: title, bounds, process, `window_id`, and optional `app_id`.
- `app`: path-free workflow and application-specific tips when recognized.
- `elements`: compact controls with `element_id`, role, text, value, enabled,
  visibility, supported patterns, and legacy `ref`.
- `stats`: tree-node count, returned count, truncation flags, and generation.
- `hint`: the next action when no elements match.

Use `include_ocr=true` only when accessible names are absent or unreliable. OCR
is local. Prefer UIA values and names when both are available.

## Action contract

Every tool returns a structured object:

```json
{
  "success": true,
  "message": "Human-readable result",
  "data": {},
  "verified": true
}
```

Failures add:

```json
{
  "error": {
    "code": "operation_failed",
    "retryable": false,
    "hint": "Actionable recovery guidance"
  }
}
```

If an element id is stale, call `snapshot` again. Do not keep trying the same id.

## Batch low-risk steps

`run_actions` accepts up to 50 typed actions and returns one final snapshot. Use
it only when the element ids and expected UI transitions are already known.
Keep `stop_on_error=true` unless later recovery actions are independently safe.

## Common application recipes

| App | Recommended approach |
|---|---|
| Notepad | Launch with a file argument, snapshot, then use the editor's `element_id`; verify with `get_value`; save with `Ctrl+S`. |
| Calculator | Snapshot buttons and the display; click exact button names or AutomationIds; read the result before the next calculation. |
| Paint | Prefer menus and UIA controls. Use canvas coordinates only as a last resort. Confirm clear, overwrite, and save operations. |
| Windows Settings | Use deep-link suffixes such as `display`, `bluetooth`, `wifi`, or `appsfeatures`. Never change security/privacy settings without explicit intent. |
| File Explorer | Open a deterministic folder with `arguments`, use `Ctrl+L` for the address bar, and avoid delete/move unless explicitly requested. |
| VS Code | Launch with a folder or file argument. `Ctrl+Shift+P` is usually better than deep menus. Re-snapshot after opening the command palette. |
| Edge / Chrome | Launch with a URL. Use `snapshot(query=...)` and `interactive_only=true`; prefer browser shortcuts for address/navigation. |
| Media Player | Launch with a media file when possible. Confirm playback state through UIA instead of assuming a transport click worked. |

## Safety rules

- Do not click destructive controls or submit forms without explicit user intent.
- Do not expose local filesystem paths in repository files or final summaries.
- Do not use coordinates when a semantic control exists.
- Do not reuse a snapshot after the visible UI changes.
- Do not assume a tool call succeeded just because it returned `success=true`;
  check `verified` and subsequent state.
