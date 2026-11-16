"""
cli_gateway.py - Unified CLI for Windows app automation.
Works with any window via --window (title) or --processname (process).

Examples:
    python cli_gateway.py --window "Notepad" discover
    python cli_gateway.py --processname notepad describe
    python cli_gateway.py --window "Notepad" click --name "Save"
    python cli_gateway.py --window "Notepad" type --text "hello"
    python cli_gateway.py --window "Notepad" dump-tree --depth 3
"""
import sys
import json
import subprocess
import argparse

from . import apps
from . import config
from . import skills_library as sk
from .driver import AppDriver


def print_result(result: dict):
    print(json.dumps(result, indent=2, ensure_ascii=False))


def _toggle_handler(driver: AppDriver, kw: dict) -> dict:
    """Handle toggle command: flip if no flag, or force --enable/--disable."""
    enable = True if kw.get("enable") else False if kw.get("disable") else None
    return sk.toggle_by_reference(
        driver,
        enable=enable,
        element_id=kw.get("element_id"),
        ref=kw.get("ref"),
        name=kw.get("name"),
        control_class=kw.get("class_name"),
        index=kw.get("index", 0),
        partial=kw.get("partial", True),
    )


def make_driver(window_title: str = None, window_class: str = None,
                process_name: str = None, window_id: str = None) -> AppDriver:
    """Create an AppDriver from --window-id, --window, or --processname."""
    if not window_id and not window_title and not process_name:
        print(
            "Error: Specify --window-id <0x...>, --window \"App Title\", "
            "or --processname <process>"
        )
        sys.exit(1)
    return AppDriver(
        window_title=window_title,
        window_class=window_class,
        process_name=process_name,
        window_id=window_id,
    )


COMMANDS = {
    "list-apps": {
        "func": lambda d, **kw: {
            "success": True,
            "message": "Supported application profiles",
            "data": {"apps": apps.list_app_profiles()},
        },
        "desc": "List supported built-in and common Windows apps",
        "args": [],
        "target_required": False,
    },
    "launch-app": {
        "func": lambda d, **kw: sk.launch_app(
            d, kw["app"], kw.get("arguments"), kw.get("timeout", 12)
        ),
        "desc": "Launch a supported app and bind its window",
        "args": [
            {"name": "--app", "type": str, "required": True, "help": "App id from list-apps"},
            {"name": "--arguments", "type": str, "default": None, "help": "URL, file path, or deep-link suffix"},
            {"name": "--timeout", "type": float, "default": 12, "help": "Window discovery timeout"},
        ],
        "target_required": False,
    },
    "snapshot": {
        "func": lambda d, **kw: sk.snapshot(
            d, kw.get("depth", 20), kw.get("max_nodes", 300),
            kw.get("interactive_only", True), kw.get("query"),
            kw.get("include_ocr", False),
        ),
        "desc": "Return a compact snapshot with stable element ids",
        "args": [
            {"name": "--depth", "type": int, "default": 20, "help": "Tree depth (default 20)"},
            {"name": "--max-nodes", "type": int, "default": 300, "help": "Maximum elements (default 300)"},
            {"name": "--include-noninteractive", "action": "store_false", "dest": "interactive_only", "default": True, "help": "Include labels and containers"},
            {"name": "--query", "type": str, "default": None, "help": "Filter by visible or accessible text"},
            {"name": "--ocr", "action": "store_true", "dest": "include_ocr", "default": False, "help": "Bind OCR text before returning elements"},
        ],
    },
    "window-action": {
        "func": lambda d, **kw: sk.window_action(d, kw["window_action"]),
        "desc": "Focus, minimize, maximize, restore, or close a window",
        "args": [
            {"name": "--action", "dest": "window_action", "type": str, "required": True, "choices": ["focus", "minimize", "maximize", "restore", "close"], "help": "Window action"},
        ],
    },
    "discover": {
        "func": lambda d, **kw: sk.discover_ui(
            d, kw.get("name"), kw.get("class_name"), kw.get("depth", 2), False,
            kw.get("max_nodes", 200)
        ),
        "desc": "Discover UIA tree of a window or control",
        "args": [
            {"name": "--name", "type": str, "default": None, "help": "Control name to zoom into"},
            {"name": "--class", "type": str, "default": None, "help": "Control class to zoom into", "dest": "class_name"},
            {"name": "--depth", "type": int, "default": 2, "help": "Tree depth (default 2)"},
            {"name": "--max-nodes", "type": int, "default": 200, "help": "Maximum rendered nodes (default 200)"},
        ],
    },
    "describe": {
        "func": lambda d, **kw: sk.describe_children(d, kw.get("name"), kw.get("class_name")),
        "desc": "List direct children of window or a control (shows class, name, patterns)",
        "args": [
            {"name": "--name", "type": str, "default": None, "help": "Control name to zoom into"},
            {"name": "--class", "type": str, "default": None, "help": "Control class to zoom into", "dest": "class_name"},
        ],
    },
    "dump-tree": {
        "func": lambda d, **kw: sk.discover_ui(
            d, kw.get("name"), kw.get("class_name"), kw.get("depth", 4), True,
            kw.get("max_nodes", 500)
        ),
        "desc": "Dump full UIA tree (deeper than discover)",
        "args": [
            {"name": "--name", "type": str, "default": None, "help": "Control name to zoom into"},
            {"name": "--class", "type": str, "default": None, "help": "Control class to zoom into", "dest": "class_name"},
            {"name": "--depth", "type": int, "default": 4, "help": "Tree depth (default 4)"},
            {"name": "--max-nodes", "type": int, "default": 500, "help": "Maximum rendered nodes (default 500)"},
        ],
    },
    "ocr-scan": {
        "func": lambda d, **kw: sk.ocr_scan(
            d, kw.get("depth", 4), kw.get("max_nodes", 500),
            kw.get("min_det_confidence", 0.3),
            kw.get("min_text_confidence", 0.45),
            kw.get("max_lines", 0),
        ),
        "desc": "OCR the window and bind text to UIA control nodes",
        "args": [
            {"name": "--depth", "type": int, "default": 4, "help": "Tree depth (default 4)"},
            {"name": "--max-nodes", "type": int, "default": 500, "help": "Maximum rendered nodes (default 500)"},
            {"name": "--min-det-confidence", "type": float, "default": 0.3, "help": "Detection threshold (default 0.3)"},
            {"name": "--min-text-confidence", "type": float, "default": 0.45, "help": "Recognition threshold (default 0.45)"},
            {"name": "--max-lines", "type": int, "default": 0, "help": "Maximum lines, 0 means unlimited"},
        ],
    },
    "click": {
        "func": lambda d, **kw: sk.activate_reference(
            d, "click", kw.get("element_id"), kw.get("ref"), kw.get("name"),
            kw.get("class_name"), kw.get("index", 0), kw.get("partial", True)
        ),
        "desc": "Click a control by element id, ref, name, or class",
        "args": [
            {"name": "--element-id", "type": str, "default": None, "help": "Stable id from snapshot (recommended)"},
            {"name": "--ref", "type": str, "default": None, "help": "Legacy control ref from dump-tree/ocr-scan"},
            {"name": "--name", "type": str, "default": None, "help": "Control name fallback"},
            {"name": "--class", "type": str, "default": None, "help": "Control class fallback", "dest": "class_name"},
            {"name": "--index", "type": int, "default": 0, "help": "Nth match (default 0)"},
            {"name": "--exact", "action": "store_false", "dest": "partial", "default": True, "help": "Require an exact name match"},
        ],
    },
    "toggle": {
        "func": lambda d, **kw: _toggle_handler(d, kw),
        "desc": "Toggle a checkbox/switch (default: flip current state)",
        "args": [
            {"name": "--element-id", "type": str, "default": None, "help": "Stable id from snapshot"},
            {"name": "--ref", "type": str, "default": None, "help": "Legacy control ref"},
            {"name": "--name", "type": str, "default": None, "help": "Control name fallback"},
            {"name": "--class", "type": str, "default": None, "help": "Control class fallback", "dest": "class_name"},
            {"name": "--enable", "action": "store_true", "default": None, "help": "Force checked state"},
            {"name": "--disable", "action": "store_true", "default": None, "dest": "disable", "help": "Force unchecked state"},
            {"name": "--index", "type": int, "default": 0, "help": "Nth match (default 0)"},
            {"name": "--exact", "action": "store_false", "dest": "partial", "default": True, "help": "Require an exact name match"},
        ],
    },
    "type": {
        "func": lambda d, **kw: sk.type_text_by_reference(
            d, kw["text"], kw.get("element_id"), kw.get("ref"), kw.get("name"),
            kw.get("class_name"), kw.get("index", 0), kw.get("partial", True)
        ),
        "desc": "Type text into an element id/locator or the focused control",
        "args": [
            {"name": "--text", "type": str, "required": True, "help": "Text to type"},
            {"name": "--element-id", "type": str, "default": None, "help": "Stable id from snapshot"},
            {"name": "--ref", "type": str, "default": None, "help": "Legacy control ref"},
            {"name": "--name", "type": str, "default": None, "help": "Target control name fallback"},
            {"name": "--class", "type": str, "default": None, "help": "Target control class fallback", "dest": "class_name"},
            {"name": "--index", "type": int, "default": 0, "help": "Nth match (default 0)"},
            {"name": "--exact", "action": "store_false", "dest": "partial", "default": True, "help": "Require an exact name match"},
        ],
    },
    "set-value": {
        "func": lambda d, **kw: sk.set_value_by_reference(
            d, kw["value"], kw.get("element_id"), kw.get("ref"), kw.get("name"),
            kw.get("class_name"), kw.get("index", 0), kw.get("partial", True)
        ),
        "desc": "Set and verify a value-capable control",
        "args": [
            {"name": "--value", "type": str, "required": True, "help": "Value to set"},
            {"name": "--element-id", "type": str, "default": None, "help": "Stable id from snapshot"},
            {"name": "--ref", "type": str, "default": None, "help": "Legacy control ref"},
            {"name": "--name", "type": str, "default": None, "help": "Control name fallback"},
            {"name": "--class", "type": str, "default": None, "help": "Control class fallback", "dest": "class_name"},
            {"name": "--index", "type": int, "default": 0, "help": "Nth match (default 0)"},
            {"name": "--exact", "action": "store_false", "dest": "partial", "default": True, "help": "Require an exact name match"},
        ],
    },
    "get-value": {
        "func": lambda d, **kw: sk.get_value_by_reference(
            d, kw.get("element_id"), kw.get("ref"), kw.get("name"),
            kw.get("class_name"), kw.get("index", 0), kw.get("partial", True)
        ),
        "desc": "Read a value-capable control",
        "args": [
            {"name": "--element-id", "type": str, "default": None, "help": "Stable id from snapshot"},
            {"name": "--ref", "type": str, "default": None, "help": "Legacy control ref"},
            {"name": "--name", "type": str, "default": None, "help": "Control name fallback"},
            {"name": "--class", "type": str, "default": None, "help": "Control class fallback", "dest": "class_name"},
            {"name": "--index", "type": int, "default": 0, "help": "Nth match (default 0)"},
            {"name": "--exact", "action": "store_false", "dest": "partial", "default": True, "help": "Require an exact name match"},
        ],
    },
    "combo-select": {
        "func": lambda d, **kw: sk.combo_select_by_reference(
            d, kw["item"], kw.get("element_id"), kw.get("ref"), kw.get("name"),
            kw.get("class_name"), kw.get("index", 0), kw.get("partial", True)
        ),
        "desc": "Select and verify a combobox item",
        "args": [
            {"name": "--item", "type": str, "required": True, "help": "Item text to select"},
            {"name": "--element-id", "type": str, "default": None, "help": "Stable id from snapshot"},
            {"name": "--ref", "type": str, "default": None, "help": "Legacy control ref"},
            {"name": "--name", "type": str, "default": None, "help": "Combobox name fallback"},
            {"name": "--class", "type": str, "default": None, "help": "Combobox class fallback", "dest": "class_name"},
            {"name": "--index", "type": int, "default": 0, "help": "Nth matching combobox (default 0)"},
            {"name": "--exact", "action": "store_false", "dest": "partial", "default": True, "help": "Require an exact combobox name match"},
        ],
    },
    "state": {
        "func": lambda d, **kw: sk.get_window_state(d),
        "desc": "Get window state (position, size, minimized)",
        "args": [],
    },
    "inspect": {
        "func": None,  # Handled specially — launches Accessibility Insights
        "desc": "Launch Accessibility Insights to inspect a window's UIA tree",
        "args": [],
    },

    # ── Mouse ──
    "double-click": {
        "func": lambda d, **kw: sk.activate_reference(
            d, "double_click", kw.get("element_id"), kw.get("ref"), kw.get("name"),
            kw.get("class_name"), kw.get("index", 0), kw.get("partial", True)
        ),
        "desc": "Double-click by element id, ref, name, or class",
        "args": [
            {"name": "--element-id", "type": str, "default": None, "help": "Stable id from snapshot (recommended)"},
            {"name": "--ref", "type": str, "default": None, "help": "Control ref from dump-tree/ocr-scan"},
            {"name": "--name", "type": str, "default": None, "help": "Control name"},
            {"name": "--class", "type": str, "default": None, "help": "Control class name", "dest": "class_name"},
            {"name": "--index", "type": int, "default": 0, "help": "Nth match (default 0)"},
            {"name": "--exact", "action": "store_false", "dest": "partial", "default": True, "help": "Require an exact name match"},
        ],
    },
    "right-click": {
        "func": lambda d, **kw: sk.activate_reference(
            d, "right_click", kw.get("element_id"), kw.get("ref"), kw.get("name"),
            kw.get("class_name"), kw.get("index", 0), kw.get("partial", True)
        ),
        "desc": "Right-click by element id, ref, name, or class",
        "args": [
            {"name": "--element-id", "type": str, "default": None, "help": "Stable id from snapshot (recommended)"},
            {"name": "--ref", "type": str, "default": None, "help": "Control ref from dump-tree/ocr-scan"},
            {"name": "--name", "type": str, "default": None, "help": "Control name"},
            {"name": "--class", "type": str, "default": None, "help": "Control class name", "dest": "class_name"},
            {"name": "--index", "type": int, "default": 0, "help": "Nth match (default 0)"},
            {"name": "--exact", "action": "store_false", "dest": "partial", "default": True, "help": "Require an exact name match"},
        ],
    },
    "hover": {
        "func": lambda d, **kw: sk.activate_reference(
            d, "hover", kw.get("element_id"), kw.get("ref"), kw.get("name"),
            kw.get("class_name"), kw.get("index", 0), kw.get("partial", True)
        ),
        "desc": "Hover by element id, ref, name, or class",
        "args": [
            {"name": "--element-id", "type": str, "default": None, "help": "Stable id from snapshot (recommended)"},
            {"name": "--ref", "type": str, "default": None, "help": "Control ref from dump-tree/ocr-scan"},
            {"name": "--name", "type": str, "default": None, "help": "Control name"},
            {"name": "--class", "type": str, "default": None, "help": "Control class name", "dest": "class_name"},
            {"name": "--index", "type": int, "default": 0, "help": "Nth match (default 0)"},
            {"name": "--exact", "action": "store_false", "dest": "partial", "default": True, "help": "Require an exact name match"},
        ],
    },

    # ── Scroll ──
    "scroll-up": {
        "func": lambda d, **kw: sk.scroll_by_reference(
            d, "up", kw.get("count", 3), kw.get("element_id"),
            kw.get("ref"), kw.get("name"), kw.get("class_name"),
            kw.get("index", 0), kw.get("partial", True)
        ),
        "desc": "Scroll up on an element id or the window",
        "args": [
            {"name": "--element-id", "type": str, "default": None, "help": "Stable id from snapshot"},
            {"name": "--ref", "type": str, "default": None, "help": "Legacy control ref"},
            {"name": "--name", "type": str, "default": None, "help": "Target control name (omit for window)"},
            {"name": "--class", "type": str, "default": None, "help": "Target control class", "dest": "class_name"},
            {"name": "--index", "type": int, "default": 0, "help": "Nth match"},
            {"name": "--exact", "action": "store_false", "dest": "partial", "default": True, "help": "Exact name match"},
            {"name": "--count", "type": int, "default": 3, "help": "Number of scroll ticks (default 3)"},
        ],
    },
    "scroll-down": {
        "func": lambda d, **kw: sk.scroll_by_reference(
            d, "down", kw.get("count", 3), kw.get("element_id"),
            kw.get("ref"), kw.get("name"), kw.get("class_name"),
            kw.get("index", 0), kw.get("partial", True)
        ),
        "desc": "Scroll down on an element id or the window",
        "args": [
            {"name": "--element-id", "type": str, "default": None, "help": "Stable id from snapshot"},
            {"name": "--ref", "type": str, "default": None, "help": "Legacy control ref"},
            {"name": "--name", "type": str, "default": None, "help": "Target control name (omit for window)"},
            {"name": "--class", "type": str, "default": None, "help": "Target control class", "dest": "class_name"},
            {"name": "--index", "type": int, "default": 0, "help": "Nth match"},
            {"name": "--exact", "action": "store_false", "dest": "partial", "default": True, "help": "Exact name match"},
            {"name": "--count", "type": int, "default": 3, "help": "Number of scroll ticks (default 3)"},
        ],
    },

    # ── Keyboard ──
    "key": {
        "func": lambda d, **kw: sk.send_key(d, kw["key"]),
        "desc": "Send a single key press (e.g. {Enter}, {Escape}, {Tab}, a)",
        "args": [
            {"name": "--key", "type": str, "required": True, "help": "Key to send (use {Enter} for special keys)"},
        ],
    },
    "hotkey": {
        "func": lambda d, **kw: sk.send_hotkey(d, kw["keys"]),
        "desc": "Send a key combination (e.g. Ctrl+c, Alt+F4, Ctrl+Shift+s)",
        "args": [
            {"name": "--keys", "type": str, "required": True, "help": "Key combo, separated by + (e.g. Ctrl+c)"},
        ],
    },
    "long-press": {
        "func": lambda d, **kw: sk.long_press_key(d, kw["key"], kw.get("duration", 1.0)),
        "desc": "Hold a key down for a duration, then release",
        "args": [
            {"name": "--key", "type": str, "required": True, "help": "Key to hold"},
            {"name": "--duration", "type": float, "default": 1.0, "help": "Hold duration in seconds (default 1.0)"},
        ],
    },

    # ── Info ──
    "list-windows": {
        "func": lambda d, **kw: sk.list_windows(d),
        "desc": "List all top-level windows on the desktop",
        "args": [],
        "target_required": False,
    },
    "get-rect": {
        "func": lambda d, **kw: sk.get_control_rect(d, kw.get("name"), kw.get("class_name")),
        "desc": "Get bounding rectangle of a control",
        "args": [
            {"name": "--name", "type": str, "default": None, "help": "Control name"},
            {"name": "--class", "type": str, "default": None, "help": "Control class name", "dest": "class_name"},
        ],
    },
    "get-text": {
        "func": lambda d, **kw: sk.get_value_by_reference(
            d, kw.get("element_id"), kw.get("ref"), kw.get("name"),
            kw.get("class_name"), kw.get("index", 0), kw.get("partial", True)
        ),
        "desc": "Read the Name text of a control (labels, headers, buttons)",
        "args": [
            {"name": "--element-id", "type": str, "default": None, "help": "Stable id from snapshot"},
            {"name": "--ref", "type": str, "default": None, "help": "Legacy control ref"},
            {"name": "--name", "type": str, "default": None, "help": "Control name fallback"},
            {"name": "--class", "type": str, "default": None, "help": "Control class fallback", "dest": "class_name"},
            {"name": "--index", "type": int, "default": 0, "help": "Nth match (default 0)"},
            {"name": "--exact", "action": "store_false", "dest": "partial", "default": True, "help": "Require an exact name match"},
        ],
    },
    "find": {
        "func": lambda d, **kw: sk.find_control(
            d, kw.get("name"), kw.get("class_name"), kw.get("partial", True),
            kw.get("limit", 20), kw.get("offset", 0)
        ),
        "desc": "Find controls by name or class without clicking",
        "args": [
            {"name": "--name", "type": str, "default": None, "help": "Control name"},
            {"name": "--class", "type": str, "default": None, "help": "Control class name", "dest": "class_name"},
            {"name": "--exact", "action": "store_false", "dest": "partial", "default": True, "help": "Require an exact name or class match"},
            {"name": "--limit", "type": int, "default": 20, "help": "Maximum matches to return (default 20)"},
            {"name": "--offset", "type": int, "default": 0, "help": "Match offset for paging"},
        ],
    },
    "focus": {
        "func": lambda d, **kw: sk.focus_window(d),
        "desc": "Bring the window to the foreground",
        "args": [],
    },
    "wait-for": {
        "func": lambda d, **kw: sk.wait_for_control(
            d, kw.get("name"), kw.get("class_name"), kw.get("timeout", 10),
            kw.get("disappear", False), kw.get("actionable", True),
            kw.get("stable", True), kw.get("partial", True)
        ),
        "desc": "Wait for a control to appear or disappear",
        "args": [
            {"name": "--name", "type": str, "default": None, "help": "Control name"},
            {"name": "--class", "type": str, "default": None, "help": "Control class name", "dest": "class_name"},
            {"name": "--timeout", "type": float, "default": 10, "help": "Timeout in seconds (default 10)"},
            {"name": "--disappear", "action": "store_true", "default": False, "help": "Wait for control to disappear instead of appear"},
            {"name": "--include-non-actionable", "action": "store_false", "dest": "actionable", "default": True, "help": "Include hidden or disabled controls"},
            {"name": "--no-stable", "action": "store_false", "dest": "stable", "default": True, "help": "Return on the first matching sample"},
            {"name": "--exact", "action": "store_false", "dest": "partial", "default": True, "help": "Require an exact name or class match"},
        ],
    },
}


def main():
    # ── inspect (launch Accessibility Insights) ──
    if len(sys.argv) >= 2 and sys.argv[1] == "inspect":
        ai_path = config.find_accessibility_insights()
        if not ai_path:
            print("Error: Accessibility Insights executable was not found.")
            print("Set ACCESSIBILITY_INSIGHTS_PATH or install Accessibility Insights for Windows.")
            sys.exit(1)
        print(f"Launching Accessibility Insights: {ai_path}")
        subprocess.Popen([ai_path])
        sys.exit(0)

    # ── help ──
    if len(sys.argv) >= 2 and sys.argv[1] in ("-h", "--help", "help"):
        print("Usage: python cli_gateway.py [--window-id ID | --window TITLE | --processname NAME] <command> [args]\n")
        print("Options:")
        print("  --window-id ID       Native window id from list-windows (recommended)")
        print("  --window TITLE       Window title (exact match first, then fuzzy)")
        print("  --processname NAME   Process name (e.g. notepad.exe)")
        print("  --class CLASS        Window class name filter (used with --window)\n")
        print("Commands:")
        max_len = max(len(k) for k in COMMANDS)
        for name, info in sorted(COMMANDS.items()):
            print(f"  {name:<{max_len}}  {info['desc']}")
        sys.exit(0)

    # ── Parse --window, --processname, --class ──
    window_title = None
    window_class = None
    process_name = None
    window_id = None
    filtered_argv = sys.argv[1:]

    for flag in ("--window-id", "--window", "--processname", "--class"):
        for i, arg in enumerate(filtered_argv):
            if arg == flag and i + 1 < len(filtered_argv):
                val = filtered_argv[i + 1]
                filtered_argv = filtered_argv[:i] + filtered_argv[i + 2:]
                if flag == "--window-id":
                    window_id = val
                elif flag == "--window":
                    window_title = val
                elif flag == "--processname":
                    process_name = val
                elif flag == "--class":
                    window_class = val
                break
            elif arg.startswith(flag + "="):
                val = arg.split("=", 1)[1]
                filtered_argv = filtered_argv[:i] + filtered_argv[i + 1:]
                if flag == "--window-id":
                    window_id = val
                elif flag == "--window":
                    window_title = val
                elif flag == "--processname":
                    process_name = val
                elif flag == "--class":
                    window_class = val
                break

    if not filtered_argv:
        print("Error: No command specified. Run with --help for usage.")
        sys.exit(1)

    action = filtered_argv[0]

    if action in ("-h", "--help", "help"):
        print("Usage: python cli_gateway.py [--window-id ID | --window TITLE | --processname NAME] <command> [args]")
        sys.exit(0)

    # ── Execute command ──
    if action not in COMMANDS:
        print(f"Error: Unknown command '{action}'.")
        print("Run 'python cli_gateway.py --help' to see available commands.")
        sys.exit(1)

    cmd = COMMANDS[action]
    if cmd["func"] is None:
        # inspect handled above
        sys.exit(0)

    if cmd.get("target_required", True):
        driver = make_driver(window_title, window_class, process_name, window_id)
    else:
        driver = AppDriver()


    # Parse command-specific args
    parser = argparse.ArgumentParser(prog=f"cli_gateway.py {action}", description=cmd["desc"])
    parser.add_argument("action", help=argparse.SUPPRESS)
    for arg_def in cmd["args"]:
        a = arg_def["name"]
        kwargs = {k: v for k, v in arg_def.items() if k != "name"}
        if kwargs.get("action") == "store_true":
            kwargs.pop("type", None)
        parser.add_argument(a, **kwargs)

    args = parser.parse_args(filtered_argv)
    kwargs = {k: v for k, v in vars(args).items() if k != "action" and v is not None}


    try:
        result = cmd["func"](driver, **kwargs)
        print_result(result)
    except Exception as e:
        print_result({"success": False, "message": str(e), "data": {}})
        sys.exit(1)


if __name__ == "__main__":
    main()
