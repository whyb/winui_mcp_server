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
import os
import subprocess
import argparse

import config
import skills_library as sk
from driver import AppDriver


def print_result(result: dict):
    print(json.dumps(result, indent=2, ensure_ascii=False))


def _toggle_handler(driver: AppDriver, kw: dict) -> dict:
    """Handle toggle command: flip if no flag, or force --enable/--disable."""
    if kw.get("enable"):
        return sk.toggle_by_name(driver, kw["name"], True)
    if kw.get("disable"):
        return sk.toggle_by_name(driver, kw["name"], False)
    # Neither flag: flip current state by reading ToggleState first
    matches = driver.find_by_name(kw["name"], partial=True)
    if not matches:
        return sk._fail(sk._hint_no_control(driver, kw["name"], "name"))
    ctrl = matches[0]
    try:
        current = ctrl.GetTogglePattern().ToggleState
        new_state = not bool(current)
    except Exception:
        new_state = True  # Can't read state, assume off -> toggle on
    return sk.toggle_by_name(driver, kw["name"], new_state)


def make_driver(window_title: str = None, window_class: str = None,
                process_name: str = None) -> AppDriver:
    """Create an AppDriver from --window or --processname args."""
    if not window_title and not process_name:
        print("Error: Specify --window \"App Title\" or --processname <process>")
        sys.exit(1)
    return AppDriver(
        window_title=window_title,
        window_class=window_class,
        process_name=process_name,
    )


COMMANDS = {
    "discover": {
        "func": lambda d, **kw: sk.discover_ui(d, kw.get("name"), kw.get("class_name"), kw.get("depth", 2)),
        "desc": "Discover UIA tree of a window or control",
        "args": [
            {"name": "--name", "type": str, "default": None, "help": "Control name to zoom into"},
            {"name": "--class", "type": str, "default": None, "help": "Control class to zoom into", "dest": "class_name"},
            {"name": "--depth", "type": int, "default": 2, "help": "Tree depth (default 2)"},
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
        "func": lambda d, **kw: sk.discover_ui(d, kw.get("name"), kw.get("class_name"), kw.get("depth", 4)),
        "desc": "Dump full UIA tree (deeper than discover)",
        "args": [
            {"name": "--name", "type": str, "default": None, "help": "Control name to zoom into"},
            {"name": "--class", "type": str, "default": None, "help": "Control class to zoom into", "dest": "class_name"},
            {"name": "--depth", "type": int, "default": 4, "help": "Tree depth (default 4)"},
        ],
    },
    "click": {
        "func": lambda d, **kw: (
            sk.click_by_name(d, kw["name"], kw.get("partial", True))
            if kw.get("name") else
            sk.click_by_class(d, kw["class_name"], kw.get("index", 0), kw.get("partial", True))
        ),
        "desc": "Click a control by name or class",
        "args": [
            {"name": "--name", "type": str, "default": None, "help": "Control name (substring match)"},
            {"name": "--class", "type": str, "default": None, "help": "Control class name", "dest": "class_name"},
            {"name": "--index", "type": int, "default": 0, "help": "Nth match for --class (default 0)"},
        ],
    },
    "toggle": {
        "func": lambda d, **kw: _toggle_handler(d, kw),
        "desc": "Toggle a checkbox/switch by name (default: flip current state)",
        "args": [
            {"name": "--name", "type": str, "required": True, "help": "Control name"},
            {"name": "--enable", "action": "store_true", "default": None, "help": "Force checked state"},
            {"name": "--disable", "action": "store_true", "default": None, "dest": "disable", "help": "Force unchecked state"},
        ],
    },
    "type": {
        "func": lambda d, **kw: sk.type_in(d, kw["text"], kw.get("name"), kw.get("class_name")),
        "desc": "Type text into a control (or focused element)",
        "args": [
            {"name": "--text", "type": str, "required": True, "help": "Text to type"},
            {"name": "--name", "type": str, "default": None, "help": "Target control name"},
            {"name": "--class", "type": str, "default": None, "help": "Target control class", "dest": "class_name"},
        ],
    },
    "set-value": {
        "func": lambda d, **kw: sk.set_value_by_name(d, kw["name"], kw["value"]),
        "desc": "Set value of an edit/spinbox by name",
        "args": [
            {"name": "--name", "type": str, "required": True, "help": "Control name"},
            {"name": "--value", "type": str, "required": True, "help": "Value to set"},
        ],
    },
    "get-value": {
        "func": lambda d, **kw: sk.get_value_by_name(d, kw["name"]),
        "desc": "Read value of a control by name",
        "args": [
            {"name": "--name", "type": str, "required": True, "help": "Control name"},
        ],
    },
    "combo-select": {
        "func": lambda d, **kw: sk.select_in_combo(d, kw["item"], kw.get("name"), kw.get("class_name")),
        "desc": "Select an item from a combobox",
        "args": [
            {"name": "--item", "type": str, "required": True, "help": "Item text to select"},
            {"name": "--name", "type": str, "default": None, "help": "Combobox name"},
            {"name": "--class", "type": str, "default": None, "help": "Combobox class", "dest": "class_name"},
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
        "func": lambda d, **kw: (
            sk.double_click_by_name(d, kw["name"], kw.get("partial", True))
            if kw.get("name") else
            sk.double_click_by_class(d, kw["class_name"], kw.get("index", 0), kw.get("partial", True))
        ),
        "desc": "Double-click a control by name or class",
        "args": [
            {"name": "--name", "type": str, "default": None, "help": "Control name"},
            {"name": "--class", "type": str, "default": None, "help": "Control class name", "dest": "class_name"},
            {"name": "--index", "type": int, "default": 0, "help": "Nth match for --class (default 0)"},
        ],
    },
    "right-click": {
        "func": lambda d, **kw: (
            sk.right_click_by_name(d, kw["name"], kw.get("partial", True))
            if kw.get("name") else
            sk.right_click_by_class(d, kw["class_name"], kw.get("index", 0), kw.get("partial", True))
        ),
        "desc": "Right-click a control by name or class",
        "args": [
            {"name": "--name", "type": str, "default": None, "help": "Control name"},
            {"name": "--class", "type": str, "default": None, "help": "Control class name", "dest": "class_name"},
            {"name": "--index", "type": int, "default": 0, "help": "Nth match for --class (default 0)"},
        ],
    },
    "hover": {
        "func": lambda d, **kw: (
            sk.hover_by_name(d, kw["name"], kw.get("partial", True))
            if kw.get("name") else
            sk.hover_by_class(d, kw["class_name"], kw.get("index", 0), kw.get("partial", True))
        ),
        "desc": "Hover (move mouse to) a control by name or class",
        "args": [
            {"name": "--name", "type": str, "default": None, "help": "Control name"},
            {"name": "--class", "type": str, "default": None, "help": "Control class name", "dest": "class_name"},
            {"name": "--index", "type": int, "default": 0, "help": "Nth match for --class (default 0)"},
        ],
    },

    # ── Scroll ──
    "scroll-up": {
        "func": lambda d, **kw: sk.scroll_up_by_name(d, kw.get("name"), kw.get("count", 3)),
        "desc": "Scroll up on a control or the window",
        "args": [
            {"name": "--name", "type": str, "default": None, "help": "Target control name (omit for window)"},
            {"name": "--count", "type": int, "default": 3, "help": "Number of scroll ticks (default 3)"},
        ],
    },
    "scroll-down": {
        "func": lambda d, **kw: sk.scroll_down_by_name(d, kw.get("name"), kw.get("count", 3)),
        "desc": "Scroll down on a control or the window",
        "args": [
            {"name": "--name", "type": str, "default": None, "help": "Target control name (omit for window)"},
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
        "func": lambda d, **kw: sk.get_text_by_name(d, kw["name"]),
        "desc": "Read the Name text of a control (labels, headers, buttons)",
        "args": [
            {"name": "--name", "type": str, "required": True, "help": "Control name"},
        ],
    },
    "find": {
        "func": lambda d, **kw: sk.find_control(d, kw.get("name"), kw.get("class_name")),
        "desc": "Find controls by name or class without clicking",
        "args": [
            {"name": "--name", "type": str, "default": None, "help": "Control name"},
            {"name": "--class", "type": str, "default": None, "help": "Control class name", "dest": "class_name"},
        ],
    },
    "focus": {
        "func": lambda d, **kw: sk.focus_window(d),
        "desc": "Bring the window to the foreground",
        "args": [],
    },
    "wait-for": {
        "func": lambda d, **kw: sk.wait_for_control(d, kw.get("name"), kw.get("class_name"),
                                                       kw.get("timeout", 10), kw.get("disappear", False)),
        "desc": "Wait for a control to appear or disappear",
        "args": [
            {"name": "--name", "type": str, "default": None, "help": "Control name"},
            {"name": "--class", "type": str, "default": None, "help": "Control class name", "dest": "class_name"},
            {"name": "--timeout", "type": float, "default": 10, "help": "Timeout in seconds (default 10)"},
            {"name": "--disappear", "action": "store_true", "default": False, "help": "Wait for control to disappear instead of appear"},
        ],
    },
}


def main():
    # ── inspect (launch Accessibility Insights) ──
    if len(sys.argv) >= 2 and sys.argv[1] == "inspect":
        ai_path = config.ACCESSIBILITY_INSIGHTS_PATH
        if not os.path.isfile(ai_path):
            print(f"Error: Accessibility Insights not found at:")
            print(f"  {ai_path}")
            sys.exit(1)
        print(f"Launching Accessibility Insights: {ai_path}")
        subprocess.Popen([ai_path])
        sys.exit(0)

    # ── help ──
    if len(sys.argv) >= 2 and sys.argv[1] in ("-h", "--help", "help"):
        print("Usage: python cli_gateway.py [--window TITLE | --processname NAME] <command> [args]\n")
        print("Options:")
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
    filtered_argv = sys.argv[1:]

    for flag in ("--window", "--processname", "--class"):
        for i, arg in enumerate(filtered_argv):
            if arg == flag and i + 1 < len(filtered_argv):
                val = filtered_argv[i + 1]
                filtered_argv = filtered_argv[:i] + filtered_argv[i + 2:]
                if flag == "--window":
                    window_title = val
                elif flag == "--processname":
                    process_name = val
                elif flag == "--class":
                    window_class = val
                break
            elif arg.startswith(flag + "="):
                val = arg.split("=", 1)[1]
                filtered_argv = filtered_argv[:i] + filtered_argv[i + 1:]
                if flag == "--window":
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
        print("Usage: python cli_gateway.py [--window TITLE | --processname NAME] <command> [args]")
        sys.exit(0)

    # ── Execute command ──
    if action not in COMMANDS:
        print(f"Error: Unknown command '{action}'.")
        print(f"Run 'python cli_gateway.py --help' to see available commands.")
        sys.exit(1)

    cmd = COMMANDS[action]
    if cmd["func"] is None:
        # inspect handled above
        sys.exit(0)

    driver = make_driver(window_title, window_class, process_name)

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
