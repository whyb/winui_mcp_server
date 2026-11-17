"""MCP server for agent-first Windows UI Automation.

The public tool surface prioritizes deterministic window ids and snapshot-scoped
element ids. Legacy locator and tree-ref tools remain available for compatibility.
"""
from __future__ import annotations

import json
import warnings
from typing import Any, Literal

# MCP 1.27 with pydantic-settings 2.15 emits a harmless unresolved-forward-ref
# warning for the SDK's generic lifespan field before any server code is created.
warnings.filterwarnings(
    "ignore",
    message=r"Field 'lifespan' has an incomplete definition.*",
)

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations
from pydantic import BaseModel, Field

from . import apps
from . import skills_library as sk
from .driver import AppDriver, clear_driver_cache, get_cached_driver

SERVER_INSTRUCTIONS = """\
WinUI MCP controls Windows desktop applications through UI Automation with local OCR fallback.

Recommended workflow:
1. Call list_windows or launch_app. Prefer the returned window_id when multiple windows exist.
2. Call snapshot with that window_id. Use query to narrow large UIs.
3. Act with element_id from the latest snapshot. Prefer element_id over names, classes, or coordinates.
4. Call snapshot again, get_value, or wait_for to verify the result.
5. Use run_actions only when the next several steps are already known and low risk.

Rules:
- Never reuse an element_id after the UI changes; snapshot again if it is stale.
- Re-snapshot after navigation, dialogs, mode changes, or tab/page changes.
- For Chromium or complex apps, use interactive_only=true and a focused query.
- Closing, deleting, submitting, sending, purchasing, or changing security settings requires explicit user intent.
- Do not expose or persist local filesystem paths unless the user requested them.
- If a control is inaccessible, run ocr_scan or snapshot(include_ocr=true) instead of guessing coordinates.
"""

mcp = FastMCP(
    "winui",
    instructions=SERVER_INSTRUCTIONS,
    website_url="https://github.com/whyb/winui_mcp_server",
)


def _json(result: dict) -> str:
    """Compact JSON helper retained for compatibility and diagnostics."""
    return json.dumps(result, ensure_ascii=False, separators=(",", ":"))


def _tool(
    title: str,
    *,
    read_only: bool = False,
    destructive: bool = False,
    idempotent: bool = False,
    open_world: bool = False,
):
    annotations = ToolAnnotations(
        title=title,
        readOnlyHint=read_only,
        destructiveHint=destructive,
        idempotentHint=idempotent,
        openWorldHint=open_world,
    )
    return mcp.tool(title=title, annotations=annotations, structured_output=True)


def _driver(
    window_title: str | None,
    process_name: str | None,
    window_class: str | None,
    window_id: str | None,
) -> AppDriver:
    return get_cached_driver(
        window_title=window_title,
        process_name=process_name,
        window_class=window_class,
        window_id=window_id,
    )


def _unbound_driver() -> AppDriver:
    driver = AppDriver.__new__(AppDriver)
    driver._window_title = None
    driver._process_name = None
    driver._window_class = None
    driver._window_id = None
    driver._window = None
    driver._pid = 0
    driver._hwnd = 0
    driver._search_errors = []
    driver._timeout = 5
    driver._element_refs = {}
    driver._element_identity_ids = {}
    driver._element_sequence = 0
    driver._snapshot_generation = 0
    return driver


class ActionStep(BaseModel):
    """One bounded action inside run_actions."""

    action: Literal[
        "click",
        "double_click",
        "right_click",
        "hover",
        "type_text",
        "set_value",
        "get_value",
        "key",
        "hotkey",
        "wait",
        "sleep",
        "focus_window",
    ] = Field(description="Action to execute.")
    element_id: str | None = Field(
        default=None,
        description="Stable element id from the latest snapshot.",
    )
    ref: str | None = Field(
        default=None,
        description="Legacy tree reference from dump_tree or ocr_scan.",
    )
    name: str | None = Field(default=None, description="Exact accessible name fallback.")
    control_class: str | None = Field(default=None, description="UIA class-name fallback.")
    index: int = Field(default=0, ge=0, description="Zero-based match index.")
    partial: bool = Field(default=False, description="Allow substring matching.")
    text: str | None = Field(default=None, description="Text for type_text.")
    value: str | None = Field(default=None, description="Value for set_value.")
    key: str | None = Field(default=None, description="Single key, such as {Enter}.")
    keys: str | None = Field(default=None, description="Hotkey, such as Ctrl+S.")
    timeout: float = Field(default=10, gt=0, le=120, description="Wait timeout in seconds.")
    seconds: float = Field(default=0.5, ge=0, le=10, description="Sleep duration.")
    disappear: bool = Field(default=False, description="Wait for disappearance.")
    actionable: bool = Field(default=True, description="Require a visible, enabled target.")
    stable: bool = Field(default=True, description="Require two stable samples.")


@mcp.resource("winui://guide")
def agent_guide() -> str:
    """Return the cross-client agent execution guide."""
    return SERVER_INSTRUCTIONS


@mcp.prompt()
def automate_windows_task(goal: str) -> str:
    """Create a concise, safe execution prompt for a Windows automation task."""
    return (
        "Use the winui MCP tools to accomplish this task:\\n"
        f"{goal}\\n\\n"
        "Start with launch_app or list_windows, use snapshot and element_id, "
        "verify every state-changing step, and stop before destructive actions "
        "unless the user explicitly requested them."
    )


@_tool("List Supported Applications", read_only=True)
def list_apps() -> dict[str, Any]:
    """List supported built-in and common Windows applications.

    Returns path-free app ids, aliases, process names, workflow hints, and
    installation availability. Use an app id with launch_app.
    """
    try:
        catalog = apps.list_app_profiles()
        return {
            "success": True,
            "message": f"Found {len(catalog)} supported application profiles",
            "data": {
                "apps": catalog,
                "hint": "Call launch_app(app='notepad') or list_windows for running apps.",
            },
        }
    except Exception as exc:
        return {"success": False, "message": f"Failed to list apps: {exc}", "data": {}}


@_tool("List Desktop Windows", read_only=True)
def list_windows(visible_only: bool = True, include_hidden: bool = False) -> dict[str, Any]:
    """List top-level desktop windows with deterministic window ids.

    Start here when the application is already open. Prefer window_id over a
    process or title locator when multiple windows exist.
    """
    return sk.list_windows(
        _unbound_driver(),
        visible_only=visible_only,
        include_hidden=include_hidden,
    )


@_tool("Launch Application", open_world=True)
def launch_app(
    app: str,
    arguments: str | list[str] | None = None,
    timeout: float = 12,
) -> dict[str, Any]:
    """Launch a supported app and return its bound window_id.

    Uses PATH, Windows App Paths, and registered URI protocols; no installation
    path is returned. arguments can be a URL/document/deep-link string or an
    argument list for flags such as --new-window and --user-data-dir.
    """
    return sk.launch_app(_unbound_driver(), app, arguments, timeout)


@_tool("Get Window State", read_only=True)
def get_window_state(
    window_title: str | None = None,
    process_name: str | None = None,
    window_class: str | None = None,
    window_id: str | None = None,
) -> dict[str, Any]:
    """Get the title, bounds, process, and minimized state of a window."""
    driver = _driver(window_title, process_name, window_class, window_id)
    return sk.get_window_state(driver)


@_tool("Focus Window")
def focus_window(
    window_title: str | None = None,
    process_name: str | None = None,
    window_class: str | None = None,
    window_id: str | None = None,
) -> dict[str, Any]:
    """Bring the bound window to the foreground."""
    driver = _driver(window_title, process_name, window_class, window_id)
    return sk.focus_window(driver)


@_tool("Control Window", destructive=True)
def window_action(
    action: Literal["focus", "minimize", "maximize", "restore", "close"],
    window_title: str | None = None,
    process_name: str | None = None,
    window_class: str | None = None,
    window_id: str | None = None,
) -> dict[str, Any]:
    """Focus, minimize, maximize, restore, or close a window.

    close is destructive and should only be used with explicit user intent.
    """
    driver = _driver(window_title, process_name, window_class, window_id)
    return sk.window_action(driver, action)


@_tool("Move Window")
def move_window(
    window_title: str | None = None,
    process_name: str | None = None,
    window_class: str | None = None,
    window_id: str | None = None,
    x: int | None = None,
    y: int | None = None,
    delta_x: int = 0,
    delta_y: int = 0,
    method: Literal["mouse", "setwindowpos"] = "mouse",
) -> dict[str, Any]:
    """Move the bound window by dragging its title bar or to an absolute position.

    method=mouse drags the title bar by delta_x/delta_y pixels; method=setwindowpos
    places the top-left corner at absolute x/y. Verify with get_window_state.
    """
    driver = _driver(window_title, process_name, window_class, window_id)
    return sk.move_window(
        driver, x=x, y=y, delta_x=delta_x, delta_y=delta_y, method=method
    )


@_tool("Reset Window Bindings", destructive=True)
def reset_driver() -> dict[str, Any]:
    """Clear cached window bindings and stale element references."""
    clear_driver_cache()
    return {"success": True, "message": "Driver cache reset", "data": {}}


@_tool("Snapshot UI", read_only=True)
def snapshot(
    window_title: str | None = None,
    process_name: str | None = None,
    window_class: str | None = None,
    window_id: str | None = None,
    depth: int = 20,
    max_nodes: int = 300,
    interactive_only: bool = True,
    query: str | None = None,
    include_ocr: bool = False,
) -> dict[str, Any]:
    """Return a compact UI snapshot with stable element ids.

    This is the primary discovery tool. Start interactive_only=true, then narrow
    with query for large apps. Set include_ocr=true when accessible labels are
    absent or unreliable.
    """
    driver = _driver(window_title, process_name, window_class, window_id)
    return sk.snapshot(driver, depth, max_nodes, interactive_only, query, include_ocr)


@_tool("Discover UI Tree (Legacy)", read_only=True)
def discover(
    window_title: str | None = None,
    process_name: str | None = None,
    window_class: str | None = None,
    window_id: str | None = None,
    name: str | None = None,
    control_class: str | None = None,
    depth: int = 2,
    max_nodes: int = 200,
) -> dict[str, Any]:
    """Return a summarized UIA tree. Prefer snapshot for normal agent workflows."""
    driver = _driver(window_title, process_name, window_class, window_id)
    return sk.discover_ui(driver, name, control_class, depth, False, max_nodes)


@_tool("Describe Immediate Controls (Legacy)", read_only=True)
def describe(
    window_title: str | None = None,
    process_name: str | None = None,
    window_class: str | None = None,
    window_id: str | None = None,
    name: str | None = None,
    control_class: str | None = None,
) -> dict[str, Any]:
    """List direct children of a window or control. Prefer snapshot."""
    driver = _driver(window_title, process_name, window_class, window_id)
    return sk.describe_children(driver, name, control_class)


@_tool("Dump Detailed UI Tree (Legacy)", read_only=True)
def dump_tree(
    window_title: str | None = None,
    process_name: str | None = None,
    window_class: str | None = None,
    window_id: str | None = None,
    name: str | None = None,
    control_class: str | None = None,
    depth: int = 4,
    max_nodes: int = 500,
    element_ids: bool = True,
) -> dict[str, Any]:
    """Dump a detailed bounded tree. Prefer snapshot unless hierarchy is required."""
    driver = _driver(window_title, process_name, window_class, window_id)
    try:
        target = driver.window
        if name:
            matches = driver.find_by_name(name, partial=False)
            if not matches:
                return sk._fail(sk._hint_no_control(driver, name, "name"))
            target = matches[0]
        elif control_class:
            matches = driver.find_by_class(control_class, partial=False)
            if not matches:
                return sk._fail(sk._hint_no_control(driver, control_class, "class"))
            target = matches[0]
        if element_ids:
            driver.reset_element_refs()
        tree = driver.dump_tree(
            target,
            max_depth=depth,
            detailed=True,
            max_nodes=max_nodes,
            element_ids=element_ids,
        )
        return {
            "success": True,
            "message": "UI tree dumped",
            "data": {"tree": tree, "max_nodes": max_nodes},
        }
    except Exception as exc:
        return sk._fail(f"Failed to dump tree: {exc}")


@_tool("OCR Scan", read_only=True)
def ocr_scan(
    window_title: str | None = None,
    process_name: str | None = None,
    window_class: str | None = None,
    window_id: str | None = None,
    depth: int = 4,
    max_nodes: int = 500,
    min_det_confidence: float = 0.3,
    min_text_confidence: float = 0.45,
    max_lines: int = 0,
) -> dict[str, Any]:
    """OCR the window and bind text to stable UIA element ids.

    Use only when accessible names are missing or unreliable. Results are local
    and no image is sent to an external service.
    """
    driver = _driver(window_title, process_name, window_class, window_id)
    return sk.ocr_scan(
        driver,
        depth,
        max_nodes,
        min_det_confidence,
        min_text_confidence,
        max_lines,
        element_ids=True,
    )


@_tool("Get Control Rectangle", read_only=True)
def get_control_rect(
    window_title: str | None = None,
    process_name: str | None = None,
    window_class: str | None = None,
    window_id: str | None = None,
    name: str | None = None,
    control_class: str | None = None,
) -> dict[str, Any]:
    """Get a control rectangle. Prefer semantic element ids for interactions."""
    driver = _driver(window_title, process_name, window_class, window_id)
    return sk.get_control_rect(driver, name, control_class, partial=False)


@_tool("Find Controls", read_only=True)
def find_control(
    window_title: str | None = None,
    process_name: str | None = None,
    window_class: str | None = None,
    window_id: str | None = None,
    name: str | None = None,
    control_class: str | None = None,
    partial: bool = False,
    limit: int = 20,
    offset: int = 0,
) -> dict[str, Any]:
    """Find controls without acting. Prefer snapshot and element_id."""
    driver = _driver(window_title, process_name, window_class, window_id)
    return sk.find_control(driver, name, control_class, partial, limit, offset)


def _window_args(
    window_title: str | None,
    process_name: str | None,
    window_class: str | None,
    window_id: str | None,
) -> AppDriver:
    return _driver(window_title, process_name, window_class, window_id)


@_tool("Click Control")
def click(
    window_title: str | None = None,
    process_name: str | None = None,
    window_class: str | None = None,
    window_id: str | None = None,
    element_id: str | None = None,
    ref: str | None = None,
    name: str | None = None,
    control_class: str | None = None,
    index: int = 0,
    partial: bool = False,
) -> dict[str, Any]:
    """Click by stable element_id, legacy ref, exact name, or class."""
    driver = _window_args(window_title, process_name, window_class, window_id)
    if element_id or ref:
        return sk.activate_reference(driver, "click", element_id, ref, name, control_class, index, partial)
    if name:
        return sk.click_by_name(driver, name, partial, index)
    if control_class:
        return sk.click_by_class(driver, control_class, index, partial)
    return sk._fail("Specify element_id, ref, name, or control_class.")


@_tool("Double-click Control")
def double_click(
    window_title: str | None = None,
    process_name: str | None = None,
    window_class: str | None = None,
    window_id: str | None = None,
    element_id: str | None = None,
    ref: str | None = None,
    name: str | None = None,
    control_class: str | None = None,
    index: int = 0,
    partial: bool = False,
) -> dict[str, Any]:
    """Double-click by stable element_id, legacy ref, exact name, or class."""
    driver = _window_args(window_title, process_name, window_class, window_id)
    if element_id or ref:
        return sk.activate_reference(driver, "double_click", element_id, ref, name, control_class, index, partial)
    if name:
        return sk.double_click_by_name(driver, name, partial, index)
    if control_class:
        return sk.double_click_by_class(driver, control_class, index, partial)
    return sk._fail("Specify element_id, ref, name, or control_class.")


@_tool("Right-click Control")
def right_click(
    window_title: str | None = None,
    process_name: str | None = None,
    window_class: str | None = None,
    window_id: str | None = None,
    element_id: str | None = None,
    ref: str | None = None,
    name: str | None = None,
    control_class: str | None = None,
    index: int = 0,
    partial: bool = False,
) -> dict[str, Any]:
    """Right-click by stable element_id, legacy ref, exact name, or class."""
    driver = _window_args(window_title, process_name, window_class, window_id)
    if element_id or ref:
        return sk.activate_reference(driver, "right_click", element_id, ref, name, control_class, index, partial)
    if name:
        return sk.right_click_by_name(driver, name, partial, index)
    if control_class:
        return sk.right_click_by_class(driver, control_class, index, partial)
    return sk._fail("Specify element_id, ref, name, or control_class.")


@_tool("Drag Control")
def drag_control(
    window_title: str | None = None,
    process_name: str | None = None,
    window_class: str | None = None,
    window_id: str | None = None,
    delta_x: int = 0,
    delta_y: int = 0,
    element_id: str | None = None,
    ref: str | None = None,
    name: str | None = None,
    control_class: str | None = None,
    index: int = 0,
    partial: bool = False,
) -> dict[str, Any]:
    """Drag a control such as a scrollbar thumb from its center by a pixel delta."""
    driver = _window_args(window_title, process_name, window_class, window_id)
    return sk.drag_control(
        driver, delta_x, delta_y, element_id, ref, name, control_class, index, partial
    )


@_tool("Hover Control", read_only=True)
def hover(
    window_title: str | None = None,
    process_name: str | None = None,
    window_class: str | None = None,
    window_id: str | None = None,
    element_id: str | None = None,
    ref: str | None = None,
    name: str | None = None,
    control_class: str | None = None,
    index: int = 0,
    partial: bool = False,
) -> dict[str, Any]:
    """Move the pointer over a control without clicking it."""
    driver = _window_args(window_title, process_name, window_class, window_id)
    if element_id or ref:
        return sk.activate_reference(driver, "hover", element_id, ref, name, control_class, index, partial)
    if name:
        return sk.hover_by_name(driver, name, partial, index)
    if control_class:
        return sk.hover_by_class(driver, control_class, index, partial)
    return sk._fail("Specify element_id, ref, name, or control_class.")


@_tool("Scroll Up")
def scroll_up(
    window_title: str | None = None,
    process_name: str | None = None,
    window_class: str | None = None,
    window_id: str | None = None,
    element_id: str | None = None,
    ref: str | None = None,
    name: str | None = None,
    control_class: str | None = None,
    index: int = 0,
    partial: bool = False,
    count: int = 3,
) -> dict[str, Any]:
    """Scroll up on a stable element or the bound window."""
    driver = _window_args(window_title, process_name, window_class, window_id)
    return sk.scroll_by_reference(driver, "up", count, element_id, ref, name, control_class, index, partial)


@_tool("Scroll Down")
def scroll_down(
    window_title: str | None = None,
    process_name: str | None = None,
    window_class: str | None = None,
    window_id: str | None = None,
    element_id: str | None = None,
    ref: str | None = None,
    name: str | None = None,
    control_class: str | None = None,
    index: int = 0,
    partial: bool = False,
    count: int = 3,
) -> dict[str, Any]:
    """Scroll down on a stable element or the bound window."""
    driver = _window_args(window_title, process_name, window_class, window_id)
    return sk.scroll_by_reference(driver, "down", count, element_id, ref, name, control_class, index, partial)


@_tool("Send Key")
def send_key(
    window_title: str | None = None,
    process_name: str | None = None,
    window_class: str | None = None,
    window_id: str | None = None,
    key: str = "",
) -> dict[str, Any]:
    """Send one key to the focused control in the bound app."""
    driver = _window_args(window_title, process_name, window_class, window_id)
    return sk.send_key(driver, key)


@_tool("Send Hotkey")
def send_hotkey(
    window_title: str | None = None,
    process_name: str | None = None,
    window_class: str | None = None,
    window_id: str | None = None,
    keys: str = "",
) -> dict[str, Any]:
    """Send a hotkey such as Ctrl+S, Alt+F4, or Ctrl+Shift+P."""
    driver = _window_args(window_title, process_name, window_class, window_id)
    return sk.send_hotkey(driver, keys)


@_tool("Long-press Key")
def long_press_key(
    window_title: str | None = None,
    process_name: str | None = None,
    window_class: str | None = None,
    window_id: str | None = None,
    key: str = "",
    duration: float = 1.0,
) -> dict[str, Any]:
    """Hold a key for a bounded duration, then release it."""
    driver = _window_args(window_title, process_name, window_class, window_id)
    return sk.long_press_key(driver, key, duration)


@_tool("Type Text")
def type_text(
    window_title: str | None = None,
    process_name: str | None = None,
    window_class: str | None = None,
    window_id: str | None = None,
    text: str = "",
    element_id: str | None = None,
    ref: str | None = None,
    name: str | None = None,
    control_class: str | None = None,
    index: int = 0,
    partial: bool = False,
) -> dict[str, Any]:
    """Type into element_id, a locator fallback, or the currently focused control."""
    driver = _window_args(window_title, process_name, window_class, window_id)
    return sk.type_text_by_reference(driver, text, element_id, ref, name, control_class, index, partial)


@_tool("Get Value", read_only=True)
def get_value(
    window_title: str | None = None,
    process_name: str | None = None,
    window_class: str | None = None,
    window_id: str | None = None,
    element_id: str | None = None,
    ref: str | None = None,
    name: str | None = None,
    control_class: str | None = None,
    index: int = 0,
    partial: bool = False,
) -> dict[str, Any]:
    """Read ValuePattern, or Name when ValuePattern is unavailable."""
    driver = _window_args(window_title, process_name, window_class, window_id)
    return sk.get_value_by_reference(driver, element_id, ref, name, control_class, index, partial)


@_tool("Get Text", read_only=True)
def get_text(
    window_title: str | None = None,
    process_name: str | None = None,
    window_class: str | None = None,
    window_id: str | None = None,
    element_id: str | None = None,
    ref: str | None = None,
    name: str | None = None,
    control_class: str | None = None,
    index: int = 0,
    partial: bool = False,
) -> dict[str, Any]:
    """Read displayed text from a label, header, button, or static text control."""
    driver = _window_args(window_title, process_name, window_class, window_id)
    if element_id or ref or name or control_class:
        return sk.get_value_by_reference(driver, element_id, ref, name, control_class, index, partial)
    return sk._fail("Specify element_id, ref, name, or control_class.")


@_tool("Set Value")
def set_value(
    window_title: str | None = None,
    process_name: str | None = None,
    window_class: str | None = None,
    window_id: str | None = None,
    value: str = "",
    element_id: str | None = None,
    ref: str | None = None,
    name: str | None = None,
    control_class: str | None = None,
    index: int = 0,
    partial: bool = False,
) -> dict[str, Any]:
    """Set and verify an edit, spinner, or value-capable control."""
    driver = _window_args(window_title, process_name, window_class, window_id)
    return sk.set_value_by_reference(driver, value, element_id, ref, name, control_class, index, partial)


@_tool("Toggle Control")
def toggle(
    window_title: str | None = None,
    process_name: str | None = None,
    window_class: str | None = None,
    window_id: str | None = None,
    element_id: str | None = None,
    ref: str | None = None,
    name: str | None = None,
    control_class: str | None = None,
    enable: bool | None = None,
    index: int = 0,
    partial: bool = False,
) -> dict[str, Any]:
    """Force a checkbox/switch on/off, or flip it when enable is omitted."""
    driver = _window_args(window_title, process_name, window_class, window_id)
    return sk.toggle_by_reference(driver, enable, element_id, ref, name, control_class, index, partial)


@_tool("Select Combobox Item")
def combo_select(
    window_title: str | None = None,
    process_name: str | None = None,
    window_class: str | None = None,
    window_id: str | None = None,
    item: str = "",
    element_id: str | None = None,
    ref: str | None = None,
    name: str | None = None,
    control_class: str | None = None,
    index: int = 0,
    partial: bool = False,
) -> dict[str, Any]:
    """Select and verify an item in a combobox, list, or expandable control."""
    driver = _window_args(window_title, process_name, window_class, window_id)
    return sk.combo_select_by_reference(driver, item, element_id, ref, name, control_class, index, partial)


@_tool("Wait for Control", read_only=True)
def wait_for(
    window_title: str | None = None,
    process_name: str | None = None,
    window_class: str | None = None,
    window_id: str | None = None,
    name: str | None = None,
    control_class: str | None = None,
    timeout: float = 10,
    disappear: bool = False,
    actionable: bool = True,
    stable: bool = True,
    partial: bool = False,
) -> dict[str, Any]:
    """Wait for a control to appear or disappear after an action."""
    driver = _window_args(window_title, process_name, window_class, window_id)
    return sk.wait_for_control(
        driver, name, control_class, timeout, disappear, actionable, stable, partial
    )


@_tool("Run Action Sequence", destructive=True, open_world=True)
def run_actions(
    steps: list[ActionStep],
    window_title: str | None = None,
    process_name: str | None = None,
    window_class: str | None = None,
    window_id: str | None = None,
    stop_on_error: bool = True,
    snapshot_after: bool = True,
) -> dict[str, Any]:
    """Execute up to 50 known actions in one round trip, then snapshot.

    Use this for low-risk multi-step operations where element ids are already
    known. Set stop_on_error=false only when later recovery steps are safe.
    """
    driver = _window_args(window_title, process_name, window_class, window_id)
    payload = [step.model_dump(exclude_none=True) for step in steps]
    return sk.run_actions(driver, payload, stop_on_error, snapshot_after)


def main() -> None:
    """Run the server over stdio for cross-client MCP compatibility."""
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
