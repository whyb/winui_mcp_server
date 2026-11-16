---
name: winui-automation
description: Automate Windows desktop applications through the winui MCP server. Use when a task requires launching, inspecting, clicking, typing, reading, or verifying native, UWP, Electron, or browser UI on Windows.
---

# WinUI Automation

Use the `winui` MCP server for semantic Windows UI automation.

## Workflow

1. Call `launch_app` when the target application is not running, or
   `list_windows` when it is already open.
2. Keep the returned `window_id`. Prefer it over title or process matching.
3. Call `snapshot` with `window_id`. Use `query` and
   `interactive_only=true` for large interfaces.
4. Act with `element_id` from the latest snapshot.
5. Verify with `snapshot`, `get_value`, `get_text`, or `wait_for`.
6. Re-snapshot whenever the UI or active page changes.

## Rules

- Never reuse a stale `element_id`.
- Prefer UIA names, AutomationIds, patterns, and element ids over coordinates.
- Use `include_ocr=true` only as a fallback for missing or unreliable labels.
- Use `run_actions` only for known, low-risk sequences.
- Do not perform destructive, financial, messaging, or security-sensitive actions
  without explicit user intent.
- Return concise state evidence to the user; do not expose local paths.

## Common apps

Supported profiles include Notepad, Calculator, Paint, Settings, File Explorer,
Visual Studio Code, Edge, Chrome, and Windows Media Player. Call `list_apps` for
current aliases, process names, and application-specific workflow hints.
