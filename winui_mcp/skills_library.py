"""
skills_library.py - Generic automation skill primitives.
These functions work with any AppDriver and accept locators as parameters.
App profiles wire specific locators to these generic functions.
Every skill returns {"success": bool, "message": str, "data": dict}.
"""
import time
import uiautomation as auto

from . import apps
from .capture import CaptureError, capture_window
from .driver import (
    AppDriver,
    _get_class_name,
    _get_name,
    _get_pid_from_hwnd,
    _get_process_name,
    _read_value,
    enumerate_top_level_windows,
    format_window_id,
)
from .ocr import OCRError, get_ocr_engine
from .ocr_pipeline import bind_ocr_lines, shift_ocr_lines


def _ok(msg: str, data: dict = None, verified: bool = None) -> dict:
    result = {"success": True, "message": msg, "data": data or {}}
    if verified is not None:
        result["verified"] = verified
    return result


def _fail(msg: str, data: dict = None, verified: bool = None,
          code: str = "operation_failed", retryable: bool = False,
          hint: str = None) -> dict:
    result = {
        "success": False,
        "message": msg,
        "data": data or {},
        "error": {
            "code": code,
            "retryable": bool(retryable),
            "hint": hint,
        },
    }
    if verified is not None:
        result["verified"] = verified
    return result


def _get_slider_label_text(slider_group: auto.Control) -> str:
    """Read the label text from a CTextSlider group (first CTextLabel child)."""
    for child in slider_group.GetChildren():
        if _get_class_name(child) == "CTextLabel":
            return _get_name(child)
    return ""


def _get_spinbox_edit(spinbox_group: auto.Control) -> auto.Control:
    """Find the CLineEdit inside a PorSpinbox group."""
    for child in spinbox_group.GetChildren():
        if _get_class_name(child) == "CLineEdit":
            return child
    return None


def _get_slider_track(slider_group: auto.Control) -> auto.Control:
    """Find the CSlider inside a CTextSlider group."""
    for child in slider_group.GetChildren():
        if _get_class_name(child) == "CSlider":
            return child
    return None


def _get_spinbox_group(slider_group: auto.Control) -> auto.Control:
    """Find the PorSpinbox inside a CTextSlider group."""
    for child in slider_group.GetChildren():
        if _get_class_name(child) == "PorSpinbox":
            return child
    return None


def _scroll_if_needed(driver: AppDriver, sidebar_path: tuple = None,
                      section_class: str = None) -> None:
    """Scroll sidebar to section if sidebar_path is configured."""
    if sidebar_path and section_class:
        driver.scroll_to(sidebar_path, section_class)


def _select_match(driver: AppDriver, matches: list, index: int, target: str):
    """Select an indexed match and raise a useful error for ambiguity."""
    if index < 0:
        raise IndexError(f"index must be non-negative, got {index}")
    if index >= len(matches):
        candidates = []
        for match in matches[:5]:
            info = driver._get_control_info(match)
            candidates.append({
                "class": info.get("class", ""),
                "name": info.get("name", ""),
                "auto_id": info.get("auto_id", ""),
                "control_type": info.get("control_type", ""),
            })
        raise IndexError(
            f"Only {len(matches)} controls matched '{target}', wanted index {index}. "
            f"Candidates: {candidates}"
        )
    return matches[index]


def _match_data(info: dict, matches: list, index: int) -> dict:
    """Return compact match metadata for an action result."""
    return {
        "control": info,
        "match_count": len(matches),
        "match_index": index,
        "ambiguous": len(matches) > 1,
    }


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Generic Skills
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


def get_window_state(driver: AppDriver) -> dict:
    """Get the current state of the application window."""
    try:
        win = driver.window
        rect = win.BoundingRectangle
        return _ok("Window state retrieved", {
            "title": _get_name(win),
            "class": _get_class_name(win),
            "left": rect.left, "top": rect.top,
            "right": rect.right, "bottom": rect.bottom,
            "width": rect.width(), "height": rect.height(),
            "is_minimized": bool(win.IsMinimize()),
        })
    except Exception as e:
        return _fail(f"Failed to get window state: {e}")


def click_button(driver: AppDriver, locator: tuple,
                 sidebar_path: tuple = None, section_class: str = None) -> dict:
    """Click a button control."""
    try:
        _scroll_if_needed(driver, sidebar_path, section_class)
        driver.click(locator)
        return _ok("Button clicked")
    except Exception as e:
        return _fail(f"Failed to click button: {e}")


def invoke_button(driver: AppDriver, locator: tuple,
                  sidebar_path: tuple = None, section_class: str = None) -> dict:
    """Invoke a button (tries InvokePattern first, falls back to click)."""
    try:
        _scroll_if_needed(driver, sidebar_path, section_class)
        driver.invoke(locator)
        return _ok("Button invoked")
    except Exception as e:
        return _fail(f"Failed to invoke button: {e}")


def toggle_section(driver: AppDriver, checkbox_locator: tuple, enabled: bool = True,
                   sidebar_path: tuple = None, section_class: str = None) -> dict:
    """Toggle a checkbox to enable/disable a section."""
    try:
        _scroll_if_needed(driver, sidebar_path, section_class)
        driver.toggle_checkbox(checkbox_locator, enabled)
        return _ok(f"Section {'enabled' if enabled else 'disabled'}")
    except Exception as e:
        return _fail(f"Failed to toggle section: {e}")


def select_combobox(driver: AppDriver, combo_locator: tuple, item_text: str,
                    sidebar_path: tuple = None, section_class: str = None) -> dict:
    """Select an item from a combobox by text match."""
    try:
        _scroll_if_needed(driver, sidebar_path, section_class)
        success = driver.select_combobox_item(combo_locator, item_text)
        if success:
            return _ok(f"'{item_text}' selected from dropdown")
        return _fail(f"'{item_text}' not found in dropdown")
    except Exception as e:
        return _fail(f"Failed to select from dropdown: {e}")


def set_slider(driver: AppDriver, slider_locator: tuple, value: int,
               sidebar_path: tuple = None, section_class: str = None) -> dict:
    """Set a slider value via its spinbox."""
    try:
        _scroll_if_needed(driver, sidebar_path, section_class)
        slider_ctrl = driver.resolve(slider_locator)
        spinbox = _get_spinbox_group(slider_ctrl)
        if spinbox:
            edit = _get_spinbox_edit(spinbox)
            if edit:
                edit.Click()
                time.sleep(0.1)
                edit.SendKeys("{Ctrl}a")
                time.sleep(0.05)
                edit.SendKeys(str(value))
                time.sleep(0.2)
                slider_ctrl.Click()
                time.sleep(0.2)
                return _ok(f"Slider set to {value}")
        return _fail("Could not find spinbox edit control")
    except Exception as e:
        return _fail(f"Failed to set slider: {e}")


def set_spinbox(driver: AppDriver, width_locator: tuple = None,
                height_locator: tuple = None, width: int = None, height: int = None,
                sidebar_path: tuple = None, section_class: str = None) -> dict:
    """Set width and/or height spinbox values."""
    try:
        _scroll_if_needed(driver, sidebar_path, section_class)
        results = {}
        if width is not None and width_locator:
            driver.set_value(width_locator, str(width))
            results["width"] = width
        if height is not None and height_locator:
            driver.set_value(height_locator, str(height))
            results["height"] = height
        return _ok("Custom resolution set", results)
    except Exception as e:
        return _fail(f"Failed to set spinbox: {e}")


def read_slider(driver: AppDriver, slider_locator: tuple) -> dict:
    """Read the current value from a slider control."""
    try:
        slider_ctrl = driver.resolve(slider_locator)
        label = _get_slider_label_text(slider_ctrl)
        spinbox = _get_spinbox_group(slider_ctrl)
        value = ""
        if spinbox:
            edit = _get_spinbox_edit(spinbox)
            if edit:
                try:
                    value = edit.GetValuePattern().Value
                except Exception:
                    value = _get_name(edit)
        return _ok("Slider value read", {"label": label, "value": value})
    except Exception as e:
        return _fail(f"Failed to read slider: {e}")


def get_text_by_name(driver: AppDriver, name: str, partial: bool = True,
                     index: int = 0) -> dict:
    """Read the Name text of a control (labels, headers, static text, etc.)."""
    try:
        matches = driver.find_by_name(name, partial=partial)
        if not matches:
            return _fail(f"No control found with name '{name}'")
        ctrl = _select_match(driver, matches, index, name)
        info = driver._get_control_info(ctrl)
        text = _get_name(ctrl)
        data = _match_data(info, matches, index)
        data["text"] = text
        return _ok(f"Text read from '{info['name']}'", data)
    except Exception as e:
        return _fail(f"Failed to get text from '{name}': {e}")


def wait_for_control(driver: AppDriver, name: str = None, class_name: str = None,
                     timeout: float = 10, disappear: bool = False,
                     actionable: bool = True, stable: bool = True,
                     partial: bool = True, poll_interval: float = 0.3) -> dict:
    """Wait for an actionable control to appear/disappear with stable polling."""
    import time as _time

    deadline = _time.time() + timeout
    last_signature = None
    while _time.time() < deadline:
        if name:
            matches = driver.find_by_name(name, partial=partial)
        elif class_name:
            matches = driver.find_by_class(class_name, partial=partial)
        else:
            return _fail("Must specify name or class_name")

        if actionable:
            matches = [control for control in matches if driver.is_control_actionable(control)]

        if disappear and not matches:
            return _ok("Control disappeared", {
                "name": name,
                "class": class_name,
                "actionable": actionable,
            }, verified=True)
        if not disappear and matches:
            control = matches[0]
            signature = driver.control_signature(control)
            if not stable or signature == last_signature:
                info = driver._get_control_info(control)
                return _ok("Control appeared", {
                    "control": info,
                    "actionable": actionable,
                    "stable": stable,
                }, verified=True)
            last_signature = signature
        else:
            last_signature = None

        _time.sleep(poll_interval)

    target = name or class_name
    action = "disappear" if disappear else "appear"
    return _fail(
        f"Timed out waiting for '{target}' to {action} after {timeout}s",
        {"actionable": actionable, "stable": stable, "partial": partial},
        verified=False,
    )


def find_control(driver: AppDriver, name: str = None, class_name: str = None,
                 partial: bool = True, limit: int = 20,
                 offset: int = 0) -> dict:
    """Find controls and return a bounded, compact result page."""
    try:
        if limit < 0 or offset < 0:
            return _fail("limit and offset must be non-negative")
        if name:
            matches = driver.find_by_name(name, partial=partial)
        elif class_name:
            matches = driver.find_by_class(class_name, partial=partial)
        else:
            return _fail("Must specify name or class_name")
        search_errors = driver.get_search_errors()
        if not matches:
            message = "No control found"
            if search_errors:
                message += f"; inaccessible branches: {len(search_errors)}"
            return _fail(message, {"search_errors": search_errors})
        page = matches[offset:offset + limit]
        results = [driver._get_control_info(c, detailed=False) for c in page]
        return _ok(f"Found {len(matches)} control(s)", {
            "total": len(matches),
            "offset": offset,
            "limit": limit,
            "returned": len(results),
            "truncated": offset + len(results) < len(matches),
            "search_errors": search_errors,
            "controls": results,
        })
    except Exception as e:
        return _fail(f"Failed to find control: {e}")


def focus_window(driver: AppDriver) -> dict:
    """Explicitly bring the window to the foreground."""
    try:
        driver.focus()
        win = driver.window
        return _ok("Window focused", {"title": _get_name(win)})
    except Exception as e:
        return _fail(f"Failed to focus window: {e}")


def list_sections(driver: AppDriver, content_locator: tuple) -> dict:
    """List all visible sections in a sidebar/panel."""
    try:
        driver.focus()
        content = driver.resolve(content_locator, timeout=3)
        children = content.GetChildren()
        sections = []
        for i, child in enumerate(children):
            cls = _get_class_name(child)
            name = _get_name(child)
            rect = child.BoundingRectangle
            sections.append({
                "index": i,
                "class": cls,
                "name": name,
                "visible": rect.width() > 0 and rect.height() > 0 if rect else False,
            })
        return _ok("Sections listed", {"sections": sections})
    except Exception as e:
        return _fail(f"Failed to list sections: {e}")


def click_preset(driver: AppDriver, preset_map: dict, preset_name: str,
                 sidebar_path: tuple = None, section_class: str = None) -> dict:
    """Click a named preset button from a preset->locator mapping."""
    locator_key = preset_map.get(preset_name)
    if not locator_key:
        return _fail(f"Unknown preset '{preset_name}'. Use: {list(preset_map.keys())}")
    # preset_map values are locator tuples directly
    try:
        _scroll_if_needed(driver, sidebar_path, section_class)
        driver.click(locator_key)
        return _ok(f"Preset '{preset_name}' selected")
    except Exception as e:
        return _fail(f"Failed to select preset: {e}")


def set_named_slider(driver: AppDriver, param_map: dict, parameter: str, value: int,
                     sidebar_path: tuple = None, section_class: str = None) -> dict:
    """Set a slider by named parameter. param_map maps parameter names to locator tuples."""
    locator = param_map.get(parameter)
    if not locator:
        return _fail(f"Unknown parameter '{parameter}'. Use: {list(param_map.keys())}")
    return set_slider(driver, locator, value, sidebar_path, section_class)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Dynamic UIA Discovery Skills (no profile needed)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


def discover_ui(driver: AppDriver, control_name: str = None,
                control_class: str = None, max_depth: int = 2,
                detailed: bool = False, max_nodes: int = 200) -> dict:
    """Discover a compact or detailed bounded UIA tree."""
    try:
        target = driver.window
        if control_name:
            matches = driver.find_by_name(control_name, partial=True)
            if not matches:
                return _fail(f"No control found with name containing '{control_name}'")
            target = matches[0]
        elif control_class:
            matches = driver.find_by_class(control_class, partial=True)
            if not matches:
                return _fail(f"No control found with class containing '{control_class}'")
            target = matches[0]

        tree = driver.dump_tree(
            target, max_depth=max_depth, detailed=detailed, max_nodes=max_nodes
        )
        return _ok("UI tree discovered", {
            "tree": tree,
            "detailed": detailed,
            "max_nodes": max_nodes,
        })
    except Exception as e:
        return _fail(f"Failed to discover UI: {e}")


def describe_children(driver: AppDriver, control_name: str = None,
                      control_class: str = None) -> dict:
    """
    List direct children of the window (or a named control).
    Shows each child's class, name, auto_id, control type, and supported patterns.
    """
    try:
        target = driver.window
        if control_name:
            matches = driver.find_by_name(control_name, partial=True)
            if not matches:
                return _fail(f"No control found with name containing '{control_name}'")
            target = matches[0]
        elif control_class:
            matches = driver.find_by_class(control_class, partial=True)
            if not matches:
                return _fail(f"No control found with class containing '{control_class}'")
            target = matches[0]

        children = driver.describe_children(target)
        return _ok(f"Found {len(children)} children", {
            "parent": driver._get_control_info(target),
            "children": children,
        })
    except Exception as e:
        return _fail(f"Failed to describe children: {e}")


def _hint_no_control(driver: AppDriver, target: str, by: str = "name") -> str:
    """Build an error message with a hint about available controls."""
    msg = f"No control found with {by} '{target}'."
    try:
        children = driver.window.GetChildren()
        names = [_get_name(c) for c in children if _get_name(c)]
        classes = [_get_class_name(c) for c in children if _get_class_name(c)]
        if by == "name" and classes:
            msg += f" Top-level classes: {classes[:8]}."
        elif by == "class" and names:
            msg += f" Top-level names: {names[:8]}."
        msg += " Use 'discover' or 'describe' to explore the UI tree."
    except Exception:
        pass
    return msg


def click_by_name(driver: AppDriver, name: str, partial: bool = True,
                  index: int = 0) -> dict:
    """Click a control found by its Name attribute. Searches all descendants."""
    try:
        matches = driver.find_by_name(name, partial=partial)
        if not matches:
            return _fail(_hint_no_control(driver, name, "name"))
        ctrl = _select_match(driver, matches, index, name)
        info = driver._get_control_info(ctrl)
        driver.click_control(ctrl)
        return _ok(
            f"Clicked '{info['name']}' ({info['class']}); state change not verified",
            _match_data(info, matches, index),
            verified=False,
        )
    except Exception as e:
        return _fail(f"Failed to click '{name}': {e}")


def click_by_class(driver: AppDriver, class_name: str, index: int = 0,
                   partial: bool = True) -> dict:
    """Click the Nth control matching a ClassName."""
    try:
        matches = driver.find_by_class(class_name, partial=partial)
        if not matches:
            return _fail(_hint_no_control(driver, class_name, "class"))
        ctrl = _select_match(driver, matches, index, class_name)
        info = driver._get_control_info(ctrl)
        driver.click_control(ctrl)
        return _ok(
            f"Clicked '{info['name']}' ({info['class']}); state change not verified",
            _match_data(info, matches, index),
            verified=False,
        )
    except Exception as e:
        return _fail(f"Failed to click: {e}")


def toggle_by_name(driver: AppDriver, name: str, enabled: bool = True,
                   partial: bool = True, index: int = 0) -> dict:
    """Toggle a checkbox/switch found by Name."""
    try:
        matches = driver.find_by_name(name, partial=partial)
        if not matches:
            return _fail(_hint_no_control(driver, name, "name"))
        ctrl = _select_match(driver, matches, index, name)
        info = driver._get_control_info(ctrl)
        state = driver.toggle_checkbox_by_control(ctrl, enabled)
        data = _match_data(info, matches, index)
        data.update({"requested_state": bool(enabled), "actual_state": state})
        if state is False:
            return _fail(
                f"Toggle state does not match requested state for '{info['name']}'",
                data,
                verified=True,
            )
        if state is None:
            return _ok(
                f"Toggle sent to '{info['name']}', state could not be verified",
                data,
                verified=False,
            )
        return _ok(
            f"Toggled '{info['name']}' to {'on' if enabled else 'off'}",
            data,
            verified=True,
        )
    except Exception as e:
        return _fail(f"Failed to toggle '{name}': {e}")


def type_in(driver: AppDriver, text: str, control_name: str = None,
            control_class: str = None, index: int = 0,
            partial: bool = True) -> dict:
    """Type text into a control found by name or class, or into the focused element."""
    try:
        ctrl = None
        match_count = 0
        if control_name:
            matches = driver.find_by_name(control_name, partial=partial)
            if not matches:
                return _fail(_hint_no_control(driver, control_name, "name"))
            ctrl = _select_match(driver, matches, index, control_name)
            match_count = len(matches)
        elif control_class:
            matches = driver.find_by_class(control_class, partial=partial)
            if not matches:
                return _fail(_hint_no_control(driver, control_class, "class"))
            ctrl = _select_match(driver, matches, index, control_class)
            match_count = len(matches)

        driver.type_text(text, ctrl)
        target_desc = _get_name(ctrl) if ctrl else "focused element"
        verified = None
        if ctrl is not None:
            actual = _read_value(ctrl)
            if actual is not None:
                verified = text in actual
        data = {"match_count": match_count, "match_index": index, "verified_value": verified}
        if verified is True:
            return _ok(f"Typed text into '{target_desc}'", data, verified=True)
        return _ok(
            f"Typed text into '{target_desc}', resulting value could not be verified",
            data,
            verified=False,
        )
    except Exception as e:
        return _fail(f"Failed to type text: {e}")


def select_in_combo(driver: AppDriver, item_text: str, combo_name: str = None,
                    combo_class: str = None, combo_index: int = 0,
                    partial: bool = True) -> dict:
    """Select an item from a combobox found by name or class."""
    try:
        if combo_name:
            matches = driver.find_by_name(combo_name, partial=partial)
        elif combo_class:
            matches = driver.find_by_class(combo_class, partial=partial)
        else:
            return _fail("Must specify combo_name or combo_class")

        if not matches:
            target = combo_name or combo_class
            return _fail(_hint_no_control(driver, target, "name" if combo_name else "class"))

        ctrl = _select_match(driver, matches, combo_index, combo_name or combo_class)
        info = driver._get_control_info(ctrl)
        state = driver.select_combobox_item_by_control(ctrl, item_text)
        data = _match_data(info, matches, combo_index)
        data.update({"requested_item": item_text, "selected": state})
        if state is False:
            return _fail(f"Item '{item_text}' was not selected in '{info['name']}'", data, verified=True)
        if state is None:
            return _ok(
                f"Selection sent to '{info['name']}', selection could not be verified",
                data,
                verified=False,
            )
        return _ok(f"Selected '{item_text}' from '{info['name']}'", data, verified=True)
    except Exception as e:
        return _fail(f"Failed to select from combobox: {e}")


def set_value_by_name(driver: AppDriver, name: str, value: str,
                      partial: bool = True, index: int = 0) -> dict:
    """Set the value of an edit/spinbox control found by Name."""
    try:
        matches = driver.find_by_name(name, partial=partial)
        if not matches:
            return _fail(_hint_no_control(driver, name, "name"))
        ctrl = _select_match(driver, matches, index, name)
        info = driver._get_control_info(ctrl)
        state = driver.set_value_by_control(ctrl, value)
        data = _match_data(info, matches, index)
        data.update({"requested_value": value, "verified_value": state})
        if state is False:
            return _fail(
                f"Value did not change to '{value}' on '{info['name']}'",
                data,
                verified=True,
            )
        if state is None:
            return _ok(
                f"Value sent to '{info['name']}', value could not be verified",
                data,
                verified=False,
            )
        return _ok(f"Set value '{value}' on '{info['name']}'", data, verified=True)
    except Exception as e:
        return _fail(f"Failed to set value: {e}")


def get_value_by_name(driver: AppDriver, name: str,
                      partial: bool = True, index: int = 0) -> dict:
    """Read the value of a control found by Name."""
    try:
        matches = driver.find_by_name(name, partial=partial)
        if not matches:
            return _fail(_hint_no_control(driver, name, "name"))
        ctrl = _select_match(driver, matches, index, name)
        info = driver._get_control_info(ctrl)
        value = _read_value(ctrl)
        if value is None:
            value = _get_name(ctrl)
        data = _match_data(info, matches, index)
        data["value"] = value
        return _ok(f"Value read from '{info['name']}'", data)
    except Exception as e:
        return _fail(f"Failed to get value: {e}")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Extended Skills
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


def double_click_by_name(driver: AppDriver, name: str, partial: bool = True,
                         index: int = 0) -> dict:
    """Double-click a control found by Name."""
    try:
        matches = driver.find_by_name(name, partial=partial)
        if not matches:
            return _fail(_hint_no_control(driver, name, "name"))
        ctrl = _select_match(driver, matches, index, name)
        info = driver._get_control_info(ctrl)
        driver.double_click_control(ctrl)
        return _ok(
            f"Double-clicked '{info['name']}' ({info['class']}); state change not verified",
            _match_data(info, matches, index),
            verified=False,
        )
    except Exception as e:
        return _fail(f"Failed to double-click '{name}': {e}")


def double_click_by_class(driver: AppDriver, class_name: str, index: int = 0,
                          partial: bool = True) -> dict:
    """Double-click the Nth control matching a ClassName."""
    try:
        matches = driver.find_by_class(class_name, partial=partial)
        if not matches:
            return _fail(_hint_no_control(driver, class_name, "class"))
        ctrl = _select_match(driver, matches, index, class_name)
        info = driver._get_control_info(ctrl)
        driver.double_click_control(ctrl)
        return _ok(
            f"Double-clicked '{info['name']}' ({info['class']}); state change not verified",
            _match_data(info, matches, index),
            verified=False,
        )
    except Exception as e:
        return _fail(f"Failed to double-click: {e}")


def right_click_by_name(driver: AppDriver, name: str, partial: bool = True,
                        index: int = 0) -> dict:
    """Right-click a control found by Name."""
    try:
        matches = driver.find_by_name(name, partial=partial)
        if not matches:
            return _fail(_hint_no_control(driver, name, "name"))
        ctrl = _select_match(driver, matches, index, name)
        info = driver._get_control_info(ctrl)
        driver.right_click_control(ctrl)
        return _ok(
            f"Right-clicked '{info['name']}' ({info['class']}); state change not verified",
            _match_data(info, matches, index),
            verified=False,
        )
    except Exception as e:
        return _fail(f"Failed to right-click '{name}': {e}")


def right_click_by_class(driver: AppDriver, class_name: str, index: int = 0,
                         partial: bool = True) -> dict:
    """Right-click the Nth control matching a ClassName."""
    try:
        matches = driver.find_by_class(class_name, partial=partial)
        if not matches:
            return _fail(_hint_no_control(driver, class_name, "class"))
        ctrl = _select_match(driver, matches, index, class_name)
        info = driver._get_control_info(ctrl)
        driver.right_click_control(ctrl)
        return _ok(
            f"Right-clicked '{info['name']}' ({info['class']}); state change not verified",
            _match_data(info, matches, index),
            verified=False,
        )
    except Exception as e:
        return _fail(f"Failed to right-click: {e}")


def hover_by_name(driver: AppDriver, name: str, partial: bool = True,
                  index: int = 0) -> dict:
    """Hover (move mouse to) a control found by Name."""
    try:
        matches = driver.find_by_name(name, partial=partial)
        if not matches:
            return _fail(_hint_no_control(driver, name, "name"))
        ctrl = _select_match(driver, matches, index, name)
        info = driver._get_control_info(ctrl)
        driver.hover_control(ctrl)
        return _ok(
            f"Hovering over '{info['name']}' ({info['class']}); state change not verified",
            _match_data(info, matches, index),
            verified=False,
        )
    except Exception as e:
        return _fail(f"Failed to hover '{name}': {e}")


def hover_by_class(driver: AppDriver, class_name: str, index: int = 0,
                   partial: bool = True) -> dict:
    """Hover (move mouse to) the Nth control matching a ClassName."""
    try:
        matches = driver.find_by_class(class_name, partial=partial)
        if not matches:
            return _fail(_hint_no_control(driver, class_name, "class"))
        ctrl = _select_match(driver, matches, index, class_name)
        info = driver._get_control_info(ctrl)
        driver.hover_control(ctrl)
        return _ok(
            f"Hovering over '{info['name']}' ({info['class']}); state change not verified",
            _match_data(info, matches, index),
            verified=False,
        )
    except Exception as e:
        return _fail(f"Failed to hover: {e}")


def scroll_up_by_name(driver: AppDriver, name: str = None, count: int = 3,
                      partial: bool = True) -> dict:
    """Scroll up on a control found by Name, or the window if no name given."""
    try:
        ctrl = None
        if name:
            matches = driver.find_by_name(name, partial=partial)
            if not matches:
                return _fail(_hint_no_control(driver, name, "name"))
            ctrl = matches[0]
        driver.scroll_up(ctrl, count)
        target = _get_name(ctrl) if ctrl else "window"
        return _ok(f"Scrolled up {count}x on '{target}'")
    except Exception as e:
        return _fail(f"Failed to scroll up: {e}")


def scroll_down_by_name(driver: AppDriver, name: str = None, count: int = 3,
                        partial: bool = True) -> dict:
    """Scroll down on a control found by Name, or the window if no name given."""
    try:
        ctrl = None
        if name:
            matches = driver.find_by_name(name, partial=partial)
            if not matches:
                return _fail(_hint_no_control(driver, name, "name"))
            ctrl = matches[0]
        driver.scroll_down(ctrl, count)
        target = _get_name(ctrl) if ctrl else "window"
        return _ok(f"Scrolled down {count}x on '{target}'")
    except Exception as e:
        return _fail(f"Failed to scroll down: {e}")


def send_key(driver: AppDriver, key: str) -> dict:
    """Send a single key press. E.g. '{Enter}', '{Escape}', '{Tab}', 'a'."""
    try:
        driver.send_key(key)
        return _ok(f"Sent key '{key}'", verified=False)
    except Exception as e:
        return _fail(f"Failed to send key '{key}': {e}")


def send_hotkey(driver: AppDriver, keys: str) -> dict:
    """Send a key combination. E.g. 'Ctrl+c', 'Alt+F4', 'Ctrl+Shift+s'."""
    try:
        parts = [k.strip() for k in keys.split("+")]
        driver.send_hotkey(*parts)
        return _ok(f"Sent hotkey '{keys}'", verified=False)
    except Exception as e:
        return _fail(f"Failed to send hotkey '{keys}': {e}")


def long_press_key(driver: AppDriver, key: str, duration: float = 1.0) -> dict:
    """Hold a key down for duration seconds, then release."""
    try:
        driver.long_press_key(key, duration)
        return _ok(f"Long-pressed '{key}' for {duration}s", verified=False)
    except Exception as e:
        return _fail(f"Failed to long-press '{key}': {e}")


def list_windows(driver: AppDriver, visible_only: bool = False,
                 include_hidden: bool = True) -> dict:
    """List top-level windows with deterministic window ids and app metadata."""
    try:
        import uiautomation as auto

        foreground_handle = 0
        try:
            foreground = auto.GetForegroundControl()
            top = foreground.GetTopLevelControl() if foreground else None
            foreground_handle = int(getattr(top, "NativeWindowHandle", 0) or 0)
        except Exception:
            pass

        windows = []
        seen_handles = set()

        def append_window(info, handle, pid=0, process=""):
            if not handle or handle in seen_handles:
                return
            visible = bool(info.get("visible"))
            if visible_only and not visible:
                return
            if not include_hidden and not visible:
                return
            if not process and pid:
                process = _get_process_name(pid)
            title = info.get("name") or info.get("title") or ""
            profile = apps.match_profile(title, process)
            info.update({
                "title": title,
                "window_id": format_window_id(handle),
                "handle": handle,
                "pid": pid,
                "process_name": process,
                "app_id": profile.id if profile else None,
                "foreground": bool(handle == foreground_handle),
            })
            windows.append(info)
            seen_handles.add(handle)

        for ctrl in auto.GetRootControl().GetChildren():
            if ctrl.ControlTypeName != "WindowControl":
                continue
            info = driver._get_control_info(ctrl)
            handle = int(getattr(ctrl, "NativeWindowHandle", 0) or 0)
            try:
                pid = _get_pid_from_hwnd(handle) if handle else 0
            except Exception:
                pid = 0
            append_window(info, handle, pid)

        # UIA does not consistently expose UWP frames or cloaked app windows.
        for record in enumerate_top_level_windows(visible_only=False):
            handle = int(record.get("handle") or 0)
            if not handle or handle in seen_handles:
                continue
            title = record.get("title") or ""
            if not title and record.get("class") != "ApplicationFrameWindow":
                continue
            info = None
            try:
                ctrl = auto.ControlFromHandle(handle)
                if ctrl is not None:
                    info = driver._get_control_info(ctrl)
            except Exception:
                info = None
            if info is None:
                info = {
                    "class": record.get("class", ""),
                    "name": title,
                    "title": title,
                    "auto_id": "",
                    "control_type": "WindowControl",
                    "enabled": True,
                    "rect": {
                        "left": record.get("left", 0),
                        "top": record.get("top", 0),
                        "right": record.get("right", 0),
                        "bottom": record.get("bottom", 0),
                        "width": record.get("width", 0),
                        "height": record.get("height", 0),
                    },
                    "visible": bool(record.get("visible")),
                    "offscreen": not bool(record.get("visible")),
                    "patterns": [],
                    "interactive": False,
                }
            else:
                info["name"] = info.get("name") or title
                info["title"] = title
                info["visible"] = bool(record.get("visible"))
            append_window(
                info, handle, int(record.get("pid") or 0),
                record.get("process_name", ""),
            )
        uwa_titles = {
            (item.get("title") or "").casefold()
            for item in windows
            if item.get("class") == "ApplicationFrameWindow"
        }
        windows = [
            item for item in windows
            if (item.get("title") or "").casefold() not in {"default ime", "msctfime ui"}
            and not (
                item.get("class") == "Windows.UI.Core.CoreWindow"
                and (item.get("title") or "").casefold() in uwa_titles
            )
        ]
        windows.sort(
            key=lambda item: (
                not item.get("foreground", False),
                not item.get("visible", False),
                0 if item.get("control_type") == "WindowControl" else 1,
                (item.get("process_name") or "").casefold(),
                (item.get("title") or "").casefold(),
            )
        )
        visible_count = sum(1 for item in windows if item.get("visible"))
        return _ok(
            f"Found {len(windows)} window(s), {visible_count} visible",
            {
                "windows": windows,
                "visible_count": visible_count,
                "total": len(windows),
                "hint": "Use window_id for deterministic multi-window automation.",
            },
        )
    except Exception as e:
        return _fail(f"Failed to list windows: {e}")


def get_control_rect(driver: AppDriver, name: str = None, class_name: str = None,
                     partial: bool = True) -> dict:
    """Get the bounding rectangle of a control found by Name or ClassName."""
    try:
        if name:
            matches = driver.find_by_name(name, partial=partial)
        elif class_name:
            matches = driver.find_by_class(class_name, partial=partial)
        else:
            return _fail("Must specify --name or --class")
        if not matches:
            target = name or class_name
            by = "name" if name else "class"
            return _fail(_hint_no_control(driver, target, by))
        ctrl = matches[0]
        info = driver._get_control_info(ctrl)
        return _ok(f"Rect of '{info['name']}'", {"control": info})
    except Exception as e:
        return _fail(f"Failed to get rect: {e}")



# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Agent-first Snapshot & Reference Actions
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


def _resolve_control(
    driver: AppDriver,
    element_id: str = None,
    ref: str = None,
    name: str = None,
    control_class: str = None,
    index: int = 0,
    partial: bool = False,
):
    """Resolve an action target, preferring stable element ids over locators."""
    if element_id:
        return driver.resolve_element(element_id), {"element_id": element_id}
    if ref:
        return driver.resolve_ref(ref), {"ref": ref}
    if name:
        matches = driver.find_by_name(name, partial=partial)
        if not matches:
            raise LookupError(_hint_no_control(driver, name, "name"))
        return _select_match(driver, matches, index, name), {
            "name": name,
            "index": index,
            "match_count": len(matches),
        }
    if control_class:
        matches = driver.find_by_class(control_class, partial=partial)
        if not matches:
            raise LookupError(_hint_no_control(driver, control_class, "class"))
        return _select_match(driver, matches, index, control_class), {
            "control_class": control_class,
            "index": index,
            "match_count": len(matches),
        }
    raise ValueError("Specify element_id, ref, name, or control_class")


def activate_reference(
    driver: AppDriver,
    action: str = "click",
    element_id: str = None,
    ref: str = None,
    name: str = None,
    control_class: str = None,
    index: int = 0,
    partial: bool = False,
) -> dict:
    """Run a mouse action against a stable element id or legacy locator."""
    try:
        ctrl, target = _resolve_control(
            driver, element_id, ref, name, control_class, index, partial
        )
        info = driver._get_control_info(ctrl)
        action_name = (action or "").strip().lower()
        method_names = {
            "click": "click_control",
            "double_click": "double_click_control",
            "right_click": "right_click_control",
            "hover": "hover_control",
        }
        if action_name not in method_names:
            return _fail(
                f"Unsupported element action {action!r}. "
                "Use click, double_click, right_click, or hover."
            )
        getattr(driver, method_names[action_name])(ctrl)
        label = info.get("name") or info.get("auto_id") or element_id or ref
        data = {"control": info, "target": target, "action": action_name}
        return _ok(
            f"{action_name.replace('_', ' ').title()} '{label}'; verify with snapshot",
            data,
            verified=False,
        )
    except Exception as exc:
        return _fail(f"Element action failed: {exc}")


def get_value_by_reference(
    driver: AppDriver,
    element_id: str = None,
    ref: str = None,
    name: str = None,
    control_class: str = None,
    index: int = 0,
    partial: bool = False,
) -> dict:
    """Read ValuePattern or Name through an element id or legacy locator."""
    try:
        ctrl, target = _resolve_control(
            driver, element_id, ref, name, control_class, index, partial
        )
        info = driver._get_control_info(ctrl)
        value = _read_value(ctrl)
        if value is None:
            value = _get_name(ctrl)
        return _ok(
            f"Read value from '{info.get('name') or element_id or ref}'",
            {"control": info, "target": target, "value": value},
        )
    except Exception as exc:
        return _fail(f"Failed to get value: {exc}")


def set_value_by_reference(
    driver: AppDriver,
    value: str,
    element_id: str = None,
    ref: str = None,
    name: str = None,
    control_class: str = None,
    index: int = 0,
    partial: bool = False,
) -> dict:
    """Set a value through an element id or legacy locator and verify it."""
    try:
        ctrl, target = _resolve_control(
            driver, element_id, ref, name, control_class, index, partial
        )
        info = driver._get_control_info(ctrl)
        state = driver.set_value_by_control(ctrl, value)
        data = {
            "control": info,
            "target": target,
            "requested_value": value,
            "verified_value": state,
        }
        if state is False:
            return _fail("Value did not change to the requested value", data, verified=True)
        if state is None:
            return _ok("Value sent, but the control does not expose verification", data, verified=False)
        return _ok("Value set and verified", data, verified=True)
    except Exception as exc:
        return _fail(f"Failed to set value: {exc}")


def type_text_by_reference(
    driver: AppDriver,
    text: str,
    element_id: str = None,
    ref: str = None,
    name: str = None,
    control_class: str = None,
    index: int = 0,
    partial: bool = False,
) -> dict:
    """Type into an element id/locator, or the focused control when omitted."""
    try:
        ctrl = None
        target = {"mode": "focused"}
        if element_id or ref or name or control_class:
            ctrl, target = _resolve_control(
                driver, element_id, ref, name, control_class, index, partial
            )
        driver.type_text(text, ctrl)
        info = driver._get_control_info(ctrl) if ctrl is not None else None
        actual = _read_value(ctrl) if ctrl is not None else None
        verified = text in actual if actual is not None else None
        data = {"control": info, "target": target, "verified_value": verified}
        if verified is True:
            return _ok("Text typed and verified", data, verified=True)
        return _ok("Text typed; verify with a snapshot or get_value", data, verified=False)
    except Exception as exc:
        return _fail(f"Failed to type text: {exc}")


def toggle_by_reference(
    driver: AppDriver,
    enable: bool = None,
    element_id: str = None,
    ref: str = None,
    name: str = None,
    control_class: str = None,
    index: int = 0,
    partial: bool = False,
) -> dict:
    """Set or flip a toggle control through a stable element id or locator."""
    try:
        ctrl, target = _resolve_control(
            driver, element_id, ref, name, control_class, index, partial
        )
        info = driver._get_control_info(ctrl)
        desired = enable
        if desired is None:
            try:
                current = ctrl.GetTogglePattern().ToggleState
                desired = current != 1
            except Exception:
                desired = True
        state = driver.toggle_checkbox_by_control(ctrl, bool(desired))
        data = {
            "control": info,
            "target": target,
            "requested_state": bool(desired),
            "actual_state": state,
        }
        if state is False:
            return _fail("Toggle state does not match the requested state", data, verified=True)
        if state is None:
            return _ok("Toggle sent, but state could not be verified", data, verified=False)
        return _ok(
            f"Toggle set to {'on' if desired else 'off'} and verified",
            data,
            verified=True,
        )
    except Exception as exc:
        return _fail(f"Failed to toggle control: {exc}")


def combo_select_by_reference(
    driver: AppDriver,
    item_text: str,
    element_id: str = None,
    ref: str = None,
    name: str = None,
    control_class: str = None,
    index: int = 0,
    partial: bool = False,
) -> dict:
    """Select a combobox item through a stable element id or locator."""
    try:
        ctrl, target = _resolve_control(
            driver, element_id, ref, name, control_class, index, partial
        )
        info = driver._get_control_info(ctrl)
        state = driver.select_combobox_item_by_control(ctrl, item_text)
        data = {
            "control": info,
            "target": target,
            "requested_item": item_text,
            "selected": state,
        }
        if state is False:
            return _fail("Combobox item was not selected", data, verified=True)
        if state is None:
            return _ok("Selection sent, but it could not be verified", data, verified=False)
        return _ok("Combobox item selected and verified", data, verified=True)
    except Exception as exc:
        return _fail(f"Failed to select combobox item: {exc}")


def scroll_by_reference(
    driver: AppDriver,
    direction: str = "down",
    count: int = 3,
    element_id: str = None,
    ref: str = None,
    name: str = None,
    control_class: str = None,
    index: int = 0,
    partial: bool = False,
) -> dict:
    """Scroll a stable element or the bound window."""
    try:
        if count < 1 or count > 50:
            return _fail("count must be between 1 and 50")
        ctrl = None
        target = {"mode": "window"}
        if element_id or ref or name or control_class:
            ctrl, target = _resolve_control(
                driver, element_id, ref, name, control_class, index, partial
            )
        if direction.casefold() == "up":
            driver.scroll_up(ctrl, count)
        elif direction.casefold() == "down":
            driver.scroll_down(ctrl, count)
        else:
            return _fail("direction must be 'up' or 'down'")
        return _ok(
            f"Scrolled {direction} {count} time(s)",
            {"direction": direction, "count": count, "target": target},
            verified=False,
        )
    except Exception as exc:
        return _fail(f"Failed to scroll: {exc}")


def _snapshot_item(node: dict) -> dict:
    """Convert a detailed tree node into a compact agent-facing element."""
    value = node.get("value")
    effective_text = node.get("effective_text") or value or node.get("name") or ""
    item = {
        "element_id": node.get("element_id"),
        "ref": node.get("ref"),
        "role": str(node.get("control_type") or "").replace("Control", "") or node.get("class"),
        "control_type": node.get("control_type", ""),
        "class": node.get("class", ""),
        "name": node.get("name", ""),
        "text": effective_text,
        "auto_id": node.get("auto_id", ""),
        "interactive": bool(node.get("interactive")),
        "enabled": node.get("enabled"),
        "visible": node.get("visible"),
        "offscreen": node.get("offscreen"),
        "patterns": node.get("patterns", []),
        "depth": node.get("depth", 0),
    }
    if value not in (None, ""):
        item["value"] = value
    if node.get("ocr_text"):
        item["ocr_text"] = node["ocr_text"]
        item["ocr_confidence"] = node.get("ocr_confidence")
        item["text_source"] = node.get("text_source")
    if node.get("children"):
        item["child_count"] = len(node["children"])
    if node.get("omitted_children"):
        item["omitted_children"] = node["omitted_children"]
    return item


def _flatten_snapshot(tree: dict, interactive_only: bool = True,
                      query: str = None, limit: int = 300) -> tuple[list, bool]:
    """Flatten a detailed UIA tree into a bounded list of useful elements."""
    query_folded = query.casefold().strip() if query else ""
    items = []
    truncated = {"value": False}

    def walk(node, depth=0):
        if truncated["value"]:
            return
        haystack = " ".join(
            str(node.get(key) or "")
            for key in ("name", "value", "effective_text", "ocr_text", "auto_id", "class", "control_type")
        ).casefold()
        query_match = not query_folded or query_folded in haystack
        interactive = bool(node.get("interactive"))
        include = depth > 0 and query_match and (
            not interactive_only or interactive or bool(query_folded)
        )
        if include:
            items.append(_snapshot_item(node))
            if len(items) >= limit:
                truncated["value"] = True
                return
        for child in node.get("children", []) or []:
            walk(child, depth + 1)
            if truncated["value"]:
                return

    walk(tree, 0)
    return items, truncated["value"]


def snapshot(
    driver: AppDriver,
    depth: int = 20,
    max_nodes: int = 300,
    interactive_only: bool = True,
    query: str = None,
    include_ocr: bool = False,
) -> dict:
    """Return a compact, agent-oriented snapshot of the bound window."""
    try:
        if not 0 <= depth <= 20:
            return _fail("depth must be between 0 and 20")
        if not 1 <= max_nodes <= 2000:
            return _fail("max_nodes must be between 1 and 2000")
        if query and len(query) > 500:
            return _fail("query must be 500 characters or fewer")

        if include_ocr:
            scanned = _ocr_scan_impl(
                driver, max_depth=depth, max_nodes=max_nodes,
                min_det_confidence=0.3, min_text_confidence=0.45,
                max_lines=0, element_ids=True,
            )
            if not scanned.get("success"):
                return scanned
            tree = scanned["data"]["tree"]
        else:
            driver.reset_element_refs()
            tree = driver.dump_tree(
                driver.window,
                max_depth=depth,
                detailed=True,
                max_nodes=max_nodes,
                element_ids=True,
            )

        elements, result_truncated = _flatten_snapshot(
            tree, interactive_only=interactive_only, query=query, limit=max_nodes
        )
        state = get_window_state(driver)
        window = state.get("data", {}) if state.get("success") else {}
        process_name = driver.process_name
        profile = apps.match_profile(window.get("title"), process_name)
        data = {
            "window": {
                **window,
                "window_id": driver.window_id,
                "process_name": process_name,
                "app_id": profile.id if profile else None,
            },
            "app": (
                {
                    "id": profile.id,
                    "name": profile.name,
                    "workflow": list(profile.workflow),
                    "tips": list(profile.tips),
                }
                if profile else None
            ),
            "elements": elements,
            "stats": {
                "tree_nodes": tree.get("node_count", 0),
                "returned_elements": len(elements),
                "tree_truncated": bool(tree.get("truncated")),
                "result_truncated": result_truncated,
                "interactive_only": interactive_only,
                "query": query,
                "include_ocr": include_ocr,
                "generation": driver._snapshot_generation,
            },
            "hint": (
                "Act with element_id from this result. If the UI changes or an id "
                "is stale, call snapshot again. Narrow large UIs with query."
            ),
        }
        if not elements:
            data["hint"] = (
                "No matching elements were returned. Retry with "
                "interactive_only=false, a broader query, or a greater depth."
            )
        return _ok(
            f"Snapshot returned {len(elements)} element(s) from {tree.get('node_count', 0)} node(s)",
            data,
        )
    except Exception as exc:
        return _fail(f"Failed to create snapshot: {exc}")


def run_actions(
    driver: AppDriver,
    steps: list[dict],
    stop_on_error: bool = True,
    snapshot_after: bool = True,
) -> dict:
    """Execute a bounded sequence of actions with one MCP round trip."""
    if not isinstance(steps, list) or not steps:
        return _fail("steps must be a non-empty list")
    if len(steps) > 50:
        return _fail("At most 50 actions can be executed in one call")
    results = []
    failed = False

    for index, step in enumerate(steps):
        if not isinstance(step, dict):
            result = _fail("Each action must be an object")
        else:
            action = str(step.get("action") or "").strip().lower()
            element_id = step.get("element_id")
            ref = step.get("ref")
            name = step.get("name")
            control_class = step.get("control_class")
            match_index = int(step.get("index", 0) or 0)
            partial = bool(step.get("partial", False))
            try:
                if action in {"click", "double_click", "right_click", "hover"}:
                    result = activate_reference(
                        driver, action, element_id, ref, name, control_class,
                        match_index, partial,
                    )
                elif action == "type_text":
                    result = type_text_by_reference(
                        driver, str(step.get("text", "")), element_id, ref,
                        name, control_class, match_index, partial,
                    )
                elif action == "set_value":
                    result = set_value_by_reference(
                        driver, str(step.get("value", "")), element_id, ref,
                        name, control_class, match_index, partial,
                    )
                elif action == "get_value":
                    result = get_value_by_reference(
                        driver, element_id, ref, name, control_class,
                        match_index, partial,
                    )
                elif action in {"key", "press_key"}:
                    result = send_key(driver, str(step.get("key", "")))
                elif action == "hotkey":
                    result = send_hotkey(driver, str(step.get("keys", "")))
                elif action == "wait":
                    result = wait_for_control(
                        driver,
                        name=name,
                        class_name=control_class,
                        timeout=float(step.get("timeout", 10)),
                        disappear=bool(step.get("disappear", False)),
                        actionable=bool(step.get("actionable", True)),
                        stable=bool(step.get("stable", True)),
                        partial=partial,
                    )
                elif action == "sleep":
                    seconds = max(0.0, min(float(step.get("seconds", 0.5)), 10.0))
                    time.sleep(seconds)
                    result = _ok(f"Slept for {seconds:.2f}s", {"seconds": seconds})
                elif action == "focus_window":
                    result = focus_window(driver)
                else:
                    result = _fail(
                        f"Unsupported action {action!r}. Supported actions: click, "
                        "double_click, right_click, hover, type_text, set_value, "
                        "get_value, key, hotkey, wait, sleep, focus_window."
                    )
            except Exception as exc:
                result = _fail(f"Action failed: {exc}")

        result["step"] = index
        result["action"] = step.get("action") if isinstance(step, dict) else None
        results.append(result)
        if not result.get("success"):
            failed = True
            if stop_on_error:
                break

    data = {
        "actions": results,
        "completed": sum(1 for item in results if item.get("success")),
        "failed": sum(1 for item in results if not item.get("success")),
        "stopped_early": failed and stop_on_error and len(results) < len(steps),
    }
    if snapshot_after and not failed:
        final_snapshot = snapshot(driver, max_nodes=200, interactive_only=True)
        data["snapshot"] = final_snapshot.get("data") if final_snapshot.get("success") else final_snapshot
    if failed:
        return _fail("One or more actions failed", data)
    return _ok(f"Completed {len(results)} action(s)", data)




def launch_app(driver: AppDriver, app: str, arguments: str = None,
               timeout: float = 12) -> dict:
    """Launch a catalog app and bind the resulting window without exposing paths."""
    try:
        import uiautomation as auto

        profile = apps.get_profile(app)
        baseline = {
            int(record.get("handle") or 0)
            for record in enumerate_top_level_windows(visible_only=False)
        }

        plan = apps.launch_application(app, arguments)
        deadline = time.time() + max(1.0, min(float(timeout), 60.0))
        fallback = None
        while time.time() < deadline:
            candidates = []
            for record in enumerate_top_level_windows(visible_only=True):
                try:
                    handle = int(record.get("handle") or 0)
                    title = record.get("title") or ""
                    if not handle or not title:
                        continue
                    pid = int(record.get("pid") or 0)
                    process = record.get("process_name") or ""
                    ctrl = auto.ControlFromHandle(handle)
                    info = (
                        driver._get_control_info(ctrl)
                        if ctrl is not None
                        else {
                            "class": record.get("class", ""),
                            "name": title,
                            "title": title,
                            "auto_id": "",
                            "control_type": "WindowControl",
                            "enabled": True,
                            "visible": bool(record.get("visible")),
                            "rect": {
                                "left": record.get("left", 0),
                                "top": record.get("top", 0),
                                "right": record.get("right", 0),
                                "bottom": record.get("bottom", 0),
                                "width": record.get("width", 0),
                                "height": record.get("height", 0),
                            },
                        }
                    )
                    info["name"] = info.get("name") or title
                    info["title"] = title
                    info["visible"] = bool(record.get("visible"))
                    profile_match = apps.match_profile(title, process)
                    process_match = process.casefold() in profile.process_names
                    title_match = any(
                        term.casefold() in title.casefold()
                        for term in (profile.name, *profile.aliases)
                    )
                    candidate = {
                        "window": {
                            **info,
                            "title": title,
                            "window_id": format_window_id(handle),
                            "pid": pid,
                            "process_name": process,
                            "app_id": profile_match.id if profile_match else None,
                        },
                        "new": handle not in baseline,
                        "score": (
                            (8 if process_match else 0)
                            + (4 if title_match else 0)
                            + (3 if info.get("control_type") == "WindowControl" else 0)
                        ),
                    }
                    if profile_match and profile_match.id == profile.id:
                        candidates.append(candidate)
                    elif handle not in baseline and (process_match or title_match):
                        candidates.append(candidate)
                    elif fallback is None and process_match:
                        fallback = candidate
                except Exception:
                    continue
            if candidates:
                candidates.sort(key=lambda item: (not item["new"], -item["score"]))
                chosen = candidates[0]
                return _ok(
                    f"Launched {profile.name} and bound its window",
                    {
                        "app": {"id": profile.id, "name": profile.name},
                        "window": chosen["window"],
                        "new_window": chosen["new"],
                        "reused_window": not chosen["new"],
                        "launch_kind": plan.kind,
                        "hint": "Call snapshot with this window_id before acting.",
                    },
                )
            time.sleep(0.25)

        if fallback:
            return _ok(
                f"Launched {profile.name}; an existing app window is available",
                {
                    "app": {"id": profile.id, "name": profile.name},
                    "window": fallback["window"],
                    "new_window": False,
                    "reused_window": True,
                    "launch_kind": plan.kind,
                    "hint": "Call snapshot with this window_id before acting.",
                },
                verified=False,
            )
        return _fail(
            f"Launch command was sent for {profile.name}, but no matching visible window "
            f"appeared within {timeout}s. Call list_windows to inspect open windows.",
            {"app": {"id": profile.id, "name": profile.name}, "launch_kind": plan.kind},
            verified=False,
        )
    except Exception as exc:
        return _fail(f"Failed to launch application: {exc}")


def window_action(driver: AppDriver, action: str = "focus") -> dict:
    """Focus, minimize, maximize, restore, or close the bound window."""
    try:
        action_name = (action or "focus").strip().lower()
        win = driver.window
        window_id = driver.window_id
        title = _get_name(win)
        if action_name == "focus":
            driver.focus()
        elif action_name == "minimize":
            win.Minimize()
        elif action_name == "maximize":
            win.Maximize()
        elif action_name == "restore":
            win.Restore()
        elif action_name == "close":
            driver.close_window()
        else:
            return _fail(
                f"Unsupported window action {action!r}. "
                "Use focus, minimize, maximize, restore, or close."
            )
        return _ok(
            f"Window action '{action_name}' completed",
            {"action": action_name, "window_id": window_id, "title": title},
            verified=False,
        )
    except Exception as exc:
        return _fail(f"Window action failed: {exc}")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# OCR Discovery & Annotated Tree
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


def _ocr_scan_impl(driver: AppDriver, max_depth: int = 4, max_nodes: int = 500,
                   min_det_confidence: float = 0.3,
                   min_text_confidence: float = 0.45,
                   max_lines: int = 0,
                   element_ids: bool = True) -> dict:
    """Capture the bound window, OCR it, and bind lines to UIA nodes."""
    try:
        window = driver.window
        try:
            if window.IsMinimize():
                window.Restore()
                time.sleep(0.2)
        except Exception:
            pass
        if element_ids:
            driver.reset_element_refs()
        tree = driver.dump_tree(
            window, max_depth=max_depth, detailed=True,
            max_nodes=max_nodes, element_ids=element_ids,
        )
        hwnd = getattr(driver, "_hwnd", 0) or getattr(window, "NativeWindowHandle", 0)
        capture = capture_window(hwnd)
        engine = get_ocr_engine()
        recognized = engine.recognize(
            capture.image,
            det_threshold=min_det_confidence,
            min_text_confidence=min_text_confidence,
            max_lines=max_lines,
        )
        lines = [line.as_dict() for line in recognized]
        screen_lines = shift_ocr_lines(lines, (capture.left, capture.top))
        stats, unbound = bind_ocr_lines(tree, screen_lines, (0, 0))
        return _ok(
            f"OCR scanned {stats.total} text line(s); {stats.bound} bound to controls",
            {
                "tree": tree,
                "ocr_lines": screen_lines,
                "unbound_lines": unbound,
                "binding": stats.as_dict(),
                "capture": {
                    "left": capture.left,
                    "top": capture.top,
                    "width": capture.width,
                    "height": capture.height,
                },
                "settings": {
                    "max_depth": max_depth,
                    "max_nodes": max_nodes,
                    "min_det_confidence": min_det_confidence,
                    "min_text_confidence": min_text_confidence,
                },
            },
        )
    except (CaptureError, OCRError) as exc:
        return _fail(f"OCR scan failed: {exc}")
    except Exception as exc:
        return _fail(f"OCR scan failed: {exc}")


def ocr_scan(driver: AppDriver, max_depth: int = 4, max_nodes: int = 500,
             min_det_confidence: float = 0.3,
             min_text_confidence: float = 0.45,
             max_lines: int = 0,
             element_ids: bool = True) -> dict:
    """Public OCR scan skill used by CLI and MCP."""
    return _ocr_scan_impl(
        driver,
        max_depth=max_depth,
        max_nodes=max_nodes,
        min_det_confidence=min_det_confidence,
        min_text_confidence=min_text_confidence,
        max_lines=max_lines,
        element_ids=element_ids,
    )


def click_ref(driver: AppDriver, ref: str, action: str = "click") -> dict:
    """Run a mouse action against a control tree reference from OCR/dump tree."""
    try:
        ctrl = driver.resolve_ref(ref)
        info = driver._get_control_info(ctrl)
        if action == "click":
            driver.click_control(ctrl)
        elif action == "double_click":
            driver.double_click_control(ctrl)
        elif action == "right_click":
            driver.right_click_control(ctrl)
        elif action == "hover":
            driver.hover_control(ctrl)
        else:
            return _fail(f"Unsupported ref action: {action}")
        return _ok(
            f"{action.replace('_', ' ').title()} '{info.get('effective_text') or info.get('name') or ref}'",
            {"control": info, "ref": ref, "action": action},
            verified=False,
        )
    except Exception as exc:
        return _fail(f"Failed to resolve control reference {ref!r}: {exc}")
