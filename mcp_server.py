"""
mcp_server.py - MCP (Model Context Protocol) server for Windows UI Automation.
Exposes all skills_library functions as MCP tools that any agent client can call.

Install in Claude Code settings.json:
{
  "mcpServers": {
    "winui": {
      "command": "conda",
      "args": ["run", "-n", "winui_mcp_server", "python", "D:/codes/github/winui_mcp_server/mcp_server.py"]
    }
  }
}
"""
import json
from mcp.server.fastmcp import FastMCP

from driver import get_cached_driver, clear_driver_cache
import skills_library as sk

mcp = FastMCP("winui")


def _json(result: dict) -> str:
    return json.dumps(result, indent=2, ensure_ascii=False)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Window Management
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


@mcp.tool()
def list_windows() -> str:
    """List all top-level windows on the desktop.
    Use this first to discover running applications and their window titles."""
    from driver import AppDriver
    driver = AppDriver.__new__(AppDriver)
    driver._window_title = None
    driver._process_name = None
    driver._window_class = None
    driver._window = None
    driver._timeout = 5
    return _json(sk.list_windows(driver))


@mcp.tool()
def get_window_state(window_title: str = None, process_name: str = None,
                     window_class: str = None) -> str:
    """Get the current state of a window (position, size, minimized).
    Specify either window_title or process_name."""
    driver = get_cached_driver(window_title, process_name, window_class)
    return _json(sk.get_window_state(driver))


@mcp.tool()
def focus_window(window_title: str = None, process_name: str = None,
                 window_class: str = None) -> str:
    """Bring a window to the foreground and give it focus."""
    driver = get_cached_driver(window_title, process_name, window_class)
    return _json(sk.focus_window(driver))


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# UI Discovery
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


@mcp.tool()
def discover(window_title: str = None, process_name: str = None,
             window_class: str = None, name: str = None,
             control_class: str = None, depth: int = 2) -> str:
    """Discover the UIA tree of a window or control.
    Use this to explore what controls are available before interacting.
    Shows a summary view (class, name, type) up to the given depth.
    Specify either window_title or process_name to target a window."""
    driver = get_cached_driver(window_title, process_name, window_class)
    return _json(sk.discover_ui(driver, name, control_class, depth))


@mcp.tool()
def describe(window_title: str = None, process_name: str = None,
             window_class: str = None, name: str = None,
             control_class: str = None) -> str:
    """List direct children of a window or control.
    Shows each child's class, name, auto_id, control type, and supported patterns."""
    driver = get_cached_driver(window_title, process_name, window_class)
    return _json(sk.describe_children(driver, name, control_class))


@mcp.tool()
def dump_tree(window_title: str = None, process_name: str = None,
              window_class: str = None, name: str = None,
              control_class: str = None, depth: int = 4) -> str:
    """Dump the full UIA tree structure with detailed info (rect, patterns, visibility).
    Deeper and more detailed than 'discover'. Use when you need the complete picture."""
    driver = get_cached_driver(window_title, process_name, window_class)
    return _json(sk.discover_ui(driver, name, control_class, depth))


@mcp.tool()
def get_control_rect(window_title: str = None, process_name: str = None,
                     window_class: str = None, name: str = None,
                     control_class: str = None) -> str:
    """Get the bounding rectangle of a control found by name or class.
    Returns position and size info."""
    driver = get_cached_driver(window_title, process_name, window_class)
    return _json(sk.get_control_rect(driver, name, control_class))


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Find (read-only, no click)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


@mcp.tool()
def find_control(window_title: str = None, process_name: str = None,
                 window_class: str = None, name: str = None,
                 control_class: str = None) -> str:
    """Find controls by name or class and return their info WITHOUT clicking.
    Use this to check if a control exists or to inspect multiple matches."""
    driver = get_cached_driver(window_title, process_name, window_class)
    return _json(sk.find_control(driver, name, control_class))


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Mouse Actions
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


@mcp.tool()
def click(window_title: str = None, process_name: str = None,
          window_class: str = None, name: str = None,
          control_class: str = None, index: int = 0) -> str:
    """Click a control by name or class name.
    Use 'name' for substring match on control Name, or 'control_class' for ClassName match."""
    driver = get_cached_driver(window_title, process_name, window_class)
    if name:
        return _json(sk.click_by_name(driver, name))
    return _json(sk.click_by_class(driver, control_class, index))


@mcp.tool()
def double_click(window_title: str = None, process_name: str = None,
                 window_class: str = None, name: str = None,
                 control_class: str = None, index: int = 0) -> str:
    """Double-click a control by name or class name."""
    driver = get_cached_driver(window_title, process_name, window_class)
    if name:
        return _json(sk.double_click_by_name(driver, name))
    return _json(sk.double_click_by_class(driver, control_class, index))


@mcp.tool()
def right_click(window_title: str = None, process_name: str = None,
                window_class: str = None, name: str = None,
                control_class: str = None, index: int = 0) -> str:
    """Right-click a control by name or class name."""
    driver = get_cached_driver(window_title, process_name, window_class)
    if name:
        return _json(sk.right_click_by_name(driver, name))
    return _json(sk.right_click_by_class(driver, control_class, index))


@mcp.tool()
def hover(window_title: str = None, process_name: str = None,
          window_class: str = None, name: str = None,
          control_class: str = None, index: int = 0) -> str:
    """Hover (move mouse to) a control by name or class name."""
    driver = get_cached_driver(window_title, process_name, window_class)
    if name:
        return _json(sk.hover_by_name(driver, name))
    return _json(sk.hover_by_class(driver, control_class, index))


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Scroll
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


@mcp.tool()
def scroll_up(window_title: str = None, process_name: str = None,
              window_class: str = None, name: str = None,
              count: int = 3) -> str:
    """Scroll up on a control (by name) or the window.
    'count' is the number of scroll ticks (default 3)."""
    driver = get_cached_driver(window_title, process_name, window_class)
    return _json(sk.scroll_up_by_name(driver, name, count))


@mcp.tool()
def scroll_down(window_title: str = None, process_name: str = None,
                window_class: str = None, name: str = None,
                count: int = 3) -> str:
    """Scroll down on a control (by name) or the window.
    'count' is the number of scroll ticks (default 3)."""
    driver = get_cached_driver(window_title, process_name, window_class)
    return _json(sk.scroll_down_by_name(driver, name, count))


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Keyboard
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


@mcp.tool()
def send_key(window_title: str = None, process_name: str = None,
             window_class: str = None, key: str = "") -> str:
    """Send a single key press. Use {Enter}, {Escape}, {Tab}, {Backspace},
    {Delete}, {Up}, {Down}, {Left}, {Right}, {Home}, {End}, {PgUp}, {PgDn},
    {F1}-{F12}, or a regular character like 'a', '1', ' '."""
    driver = get_cached_driver(window_title, process_name, window_class)
    return _json(sk.send_key(driver, key))


@mcp.tool()
def send_hotkey(window_title: str = None, process_name: str = None,
                window_class: str = None, keys: str = "") -> str:
    """Send a key combination. Use + to separate keys.
    Examples: 'Ctrl+c', 'Ctrl+v', 'Alt+F4', 'Ctrl+Shift+s', 'Ctrl+Alt+Delete'."""
    driver = get_cached_driver(window_title, process_name, window_class)
    return _json(sk.send_hotkey(driver, keys))


@mcp.tool()
def long_press_key(window_title: str = None, process_name: str = None,
                   window_class: str = None, key: str = "",
                   duration: float = 1.0) -> str:
    """Hold a key down for a duration (in seconds), then release.
    Useful for games or repeat actions."""
    driver = get_cached_driver(window_title, process_name, window_class)
    return _json(sk.long_press_key(driver, key, duration))


@mcp.tool()
def type_text(window_title: str = None, process_name: str = None,
              window_class: str = None, text: str = "",
              name: str = None, control_class: str = None) -> str:
    """Type text into a control (found by name/class) or the focused element.
    Use 'name' or 'control_class' to target a specific input field."""
    driver = get_cached_driver(window_title, process_name, window_class)
    return _json(sk.type_in(driver, text, name, control_class))


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Value & Toggle
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


@mcp.tool()
def get_value(window_title: str = None, process_name: str = None,
              window_class: str = None, name: str = "") -> str:
    """Read the current value of a control (edit box, spinbox, etc.) by name.
    Only works for controls that support ValuePattern (input fields, spinboxes).
    For static text labels, use 'get_text' instead."""
    driver = get_cached_driver(window_title, process_name, window_class)
    return _json(sk.get_value_by_name(driver, name))


@mcp.tool()
def get_text(window_title: str = None, process_name: str = None,
             window_class: str = None, name: str = "") -> str:
    """Read the Name text of a control (labels, headers, static text, buttons).
    Use this for controls that display text but don't support ValuePattern.
    For input fields / edit boxes, use 'get_value' instead."""
    driver = get_cached_driver(window_title, process_name, window_class)
    return _json(sk.get_text_by_name(driver, name))


@mcp.tool()
def set_value(window_title: str = None, process_name: str = None,
              window_class: str = None, name: str = "",
              value: str = "") -> str:
    """Set the value of an edit/spinbox control by name."""
    driver = get_cached_driver(window_title, process_name, window_class)
    return _json(sk.set_value_by_name(driver, name, value))


@mcp.tool()
def toggle(window_title: str = None, process_name: str = None,
           window_class: str = None, name: str = "",
           enable: bool = None) -> str:
    """Toggle a checkbox or switch by name.
    - enable=True: force to checked state
    - enable=False: force to unchecked state
    - enable=None (omit): flip the current state"""
    driver = get_cached_driver(window_title, process_name, window_class)
    if enable is None:
        # Flip: read current state, then toggle to opposite
        matches = driver.find_by_name(name, partial=True)
        if not matches:
            return _json(sk._fail(sk._hint_no_control(driver, name, "name")))
        ctrl = matches[0]
        try:
            current = ctrl.GetTogglePattern().ToggleState
            new_state = not bool(current)
        except Exception:
            new_state = True  # Can't read state, assume off -> toggle on
        return _json(sk.toggle_by_name(driver, name, new_state))
    return _json(sk.toggle_by_name(driver, name, enable))


@mcp.tool()
def combo_select(window_title: str = None, process_name: str = None,
                 window_class: str = None, item: str = "",
                 name: str = None, control_class: str = None) -> str:
    """Select an item from a combobox by text.
    Specify the combobox by 'name' or 'control_class'."""
    driver = get_cached_driver(window_title, process_name, window_class)
    return _json(sk.select_in_combo(driver, item, name, control_class))


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Wait
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


@mcp.tool()
def wait_for(window_title: str = None, process_name: str = None,
             window_class: str = None, name: str = None,
             control_class: str = None, timeout: float = 10,
             disappear: bool = False) -> str:
    """Wait for a control to appear or disappear.
    Useful for async UI loading, dialogs, or loading spinners.
    - disappear=False (default): wait until the control appears
    - disappear=True: wait until the control disappears"""
    driver = get_cached_driver(window_title, process_name, window_class)
    return _json(sk.wait_for_control(driver, name, control_class, timeout, disappear))


def main():
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
