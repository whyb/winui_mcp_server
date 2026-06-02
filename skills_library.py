"""
skills_library.py - Generic automation skill primitives.
These functions work with any AppDriver and accept locators as parameters.
App profiles wire specific locators to these generic functions.
Every skill returns {"success": bool, "message": str, "data": dict}.
"""
import time
import uiautomation as auto
from driver import AppDriver, _get_name, _get_class_name


def _ok(msg: str, data: dict = None) -> dict:
    return {"success": True, "message": msg, "data": data or {}}


def _fail(msg: str, data: dict = None) -> dict:
    return {"success": False, "message": msg, "data": data or {}}


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


def get_text_by_name(driver: AppDriver, name: str, partial: bool = True) -> dict:
    """Read the Name text of a control (labels, headers, static text, etc.)."""
    try:
        matches = driver.find_by_name(name, partial=partial)
        if not matches:
            return _fail(f"No control found with name '{name}'")
        ctrl = matches[0]
        info = driver._get_control_info(ctrl)
        text = _get_name(ctrl)
        return _ok(f"Text read from '{info['name']}'", {
            "text": text,
            "control": info,
        })
    except Exception as e:
        return _fail(f"Failed to get text from '{name}': {e}")


def wait_for_control(driver: AppDriver, name: str = None, class_name: str = None,
                     timeout: float = 10, disappear: bool = False) -> dict:
    """Wait for a control to appear or disappear."""
    import time as _time
    deadline = _time.time() + timeout
    while _time.time() < deadline:
        if name:
            matches = driver.find_by_name(name, partial=True)
        elif class_name:
            matches = driver.find_by_class(class_name, partial=True)
        else:
            return _fail("Must specify name or class_name")

        found = len(matches) > 0
        if disappear and not found:
            return _ok(f"Control disappeared", {"name": name, "class": class_name})
        if not disappear and found:
            info = driver._get_control_info(matches[0])
            return _ok(f"Control appeared", {"control": info})
        _time.sleep(0.3)

    target = name or class_name
    action = "disappear" if disappear else "appear"
    return _fail(f"Timed out waiting for '{target}' to {action} after {timeout}s")


def find_control(driver: AppDriver, name: str = None, class_name: str = None,
                 partial: bool = True) -> dict:
    """Find controls and return their info without clicking."""
    try:
        if name:
            matches = driver.find_by_name(name, partial=partial)
        elif class_name:
            matches = driver.find_by_class(class_name, partial=partial)
        else:
            return _fail("Must specify name or class_name")
        if not matches:
            return _fail(f"No control found")
        results = [driver._get_control_info(c) for c in matches]
        return _ok(f"Found {len(results)} control(s)", {"controls": results})
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
                control_class: str = None, max_depth: int = 2) -> dict:
    """
    Discover the UIA tree of the current window (or a named control within it).
    Use this to explore what controls are available before interacting.
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

        tree = driver.dump_tree(target, max_depth=max_depth)
        return _ok("UI tree discovered", {"tree": tree})
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


def click_by_name(driver: AppDriver, name: str, partial: bool = True) -> dict:
    """Click a control found by its Name attribute. Searches all descendants."""
    try:
        matches = driver.find_by_name(name, partial=partial)
        if not matches:
            return _fail(_hint_no_control(driver, name, "name"))
        ctrl = matches[0]
        info = driver._get_control_info(ctrl)
        driver.click_control(ctrl)
        return _ok(f"Clicked '{info['name']}' ({info['class']})", {"control": info})
    except Exception as e:
        return _fail(f"Failed to click '{name}': {e}")


def click_by_class(driver: AppDriver, class_name: str, index: int = 0,
                   partial: bool = True) -> dict:
    """Click the Nth control matching a ClassName."""
    try:
        matches = driver.find_by_class(class_name, partial=partial)
        if not matches:
            return _fail(_hint_no_control(driver, class_name, "class"))
        if index >= len(matches):
            return _fail(f"Only {len(matches)} controls with class '{class_name}', wanted index {index}")
        ctrl = matches[index]
        info = driver._get_control_info(ctrl)
        driver.click_control(ctrl)
        return _ok(f"Clicked '{info['name']}' ({info['class']})", {"control": info})
    except Exception as e:
        return _fail(f"Failed to click: {e}")


def toggle_by_name(driver: AppDriver, name: str, enabled: bool = True,
                   partial: bool = True) -> dict:
    """Toggle a checkbox/switch found by Name."""
    try:
        matches = driver.find_by_name(name, partial=partial)
        if not matches:
            return _fail(_hint_no_control(driver, name, "name"))
        ctrl = matches[0]
        info = driver._get_control_info(ctrl)
        driver.toggle_checkbox_by_control(ctrl, enabled)
        return _ok(f"Toggled '{info['name']}' to {'on' if enabled else 'off'}", {"control": info})
    except Exception as e:
        return _fail(f"Failed to toggle '{name}': {e}")


def type_in(driver: AppDriver, text: str, control_name: str = None,
            control_class: str = None) -> dict:
    """Type text into a control found by name or class, or into the focused element."""
    try:
        ctrl = None
        if control_name:
            matches = driver.find_by_name(control_name, partial=True)
            if not matches:
                return _fail(_hint_no_control(driver, control_name, "name"))
            ctrl = matches[0]
        elif control_class:
            matches = driver.find_by_class(control_class, partial=True)
            if not matches:
                return _fail(_hint_no_control(driver, control_class, "class"))
            ctrl = matches[0]

        driver.type_text(text, ctrl)
        target_desc = _get_name(ctrl) if ctrl else "focused element"
        return _ok(f"Typed text into '{target_desc}'")
    except Exception as e:
        return _fail(f"Failed to type text: {e}")


def select_in_combo(driver: AppDriver, item_text: str, combo_name: str = None,
                    combo_class: str = None, combo_index: int = 0) -> dict:
    """Select an item from a combobox found by name or class."""
    try:
        if combo_name:
            matches = driver.find_by_name(combo_name, partial=True)
        elif combo_class:
            matches = driver.find_by_class(combo_class, partial=True)
        else:
            return _fail("Must specify combo_name or combo_class")

        if not matches:
            target = combo_name or combo_class
            return _fail(_hint_no_control(driver, target, "name" if combo_name else "class"))

        if combo_index >= len(matches):
            return _fail(f"Only {len(matches)} comboboxes found, wanted index {combo_index}")

        ctrl = matches[combo_index]
        info = driver._get_control_info(ctrl)

        # Click to open, then search for item
        ctrl.Click()
        time.sleep(0.5)
        try:
            pattern = ctrl.GetExpandCollapsePattern()
            pattern.Expand()
            time.sleep(0.3)
        except Exception:
            pass

        # Search children and grandchildren
        for item in ctrl.GetChildren():
            if item_text.lower() in _get_name(item).lower():
                item.Click()
                time.sleep(0.3)
                return _ok(f"Selected '{item_text}' from '{info['name']}'")
            for sub in item.GetChildren():
                if item_text.lower() in _get_name(sub).lower():
                    sub.Click()
                    time.sleep(0.3)
                    return _ok(f"Selected '{item_text}' from '{info['name']}'")

        # Close if not found
        try:
            ctrl.GetExpandCollapsePattern().Collapse()
        except Exception:
            ctrl.Click()
        return _fail(f"Item '{item_text}' not found in '{info['name']}'")
    except Exception as e:
        return _fail(f"Failed to select from combobox: {e}")


def set_value_by_name(driver: AppDriver, name: str, value: str,
                      partial: bool = True) -> dict:
    """Set the value of an edit/spinbox control found by Name."""
    try:
        matches = driver.find_by_name(name, partial=partial)
        if not matches:
            return _fail(_hint_no_control(driver, name, "name"))
        ctrl = matches[0]
        info = driver._get_control_info(ctrl)
        try:
            ctrl.GetValuePattern().SetValue(value)
        except Exception:
            ctrl.Click()
            time.sleep(0.1)
            ctrl.SendKeys("{Ctrl}a")
            time.sleep(0.05)
            ctrl.SendKeys(value)
        time.sleep(0.2)
        return _ok(f"Set value '{value}' on '{info['name']}'", {"control": info})
    except Exception as e:
        return _fail(f"Failed to set value: {e}")


def get_value_by_name(driver: AppDriver, name: str,
                      partial: bool = True) -> dict:
    """Read the value of a control found by Name."""
    try:
        matches = driver.find_by_name(name, partial=partial)
        if not matches:
            return _fail(_hint_no_control(driver, name, "name"))
        ctrl = matches[0]
        info = driver._get_control_info(ctrl)
        value = ""
        try:
            value = ctrl.GetValuePattern().Value
        except Exception:
            value = _get_name(ctrl)
        return _ok(f"Value read from '{info['name']}'", {
            "value": value,
            "control": info,
        })
    except Exception as e:
        return _fail(f"Failed to get value: {e}")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Extended Skills
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


def double_click_by_name(driver: AppDriver, name: str, partial: bool = True) -> dict:
    """Double-click a control found by Name."""
    try:
        matches = driver.find_by_name(name, partial=partial)
        if not matches:
            return _fail(_hint_no_control(driver, name, "name"))
        ctrl = matches[0]
        info = driver._get_control_info(ctrl)
        driver.double_click_control(ctrl)
        return _ok(f"Double-clicked '{info['name']}' ({info['class']})", {"control": info})
    except Exception as e:
        return _fail(f"Failed to double-click '{name}': {e}")


def double_click_by_class(driver: AppDriver, class_name: str, index: int = 0,
                          partial: bool = True) -> dict:
    """Double-click the Nth control matching a ClassName."""
    try:
        matches = driver.find_by_class(class_name, partial=partial)
        if not matches:
            return _fail(_hint_no_control(driver, class_name, "class"))
        if index >= len(matches):
            return _fail(f"Only {len(matches)} controls with class '{class_name}', wanted index {index}")
        ctrl = matches[index]
        info = driver._get_control_info(ctrl)
        driver.double_click_control(ctrl)
        return _ok(f"Double-clicked '{info['name']}' ({info['class']})", {"control": info})
    except Exception as e:
        return _fail(f"Failed to double-click: {e}")


def right_click_by_name(driver: AppDriver, name: str, partial: bool = True) -> dict:
    """Right-click a control found by Name."""
    try:
        matches = driver.find_by_name(name, partial=partial)
        if not matches:
            return _fail(_hint_no_control(driver, name, "name"))
        ctrl = matches[0]
        info = driver._get_control_info(ctrl)
        driver.right_click_control(ctrl)
        return _ok(f"Right-clicked '{info['name']}' ({info['class']})", {"control": info})
    except Exception as e:
        return _fail(f"Failed to right-click '{name}': {e}")


def right_click_by_class(driver: AppDriver, class_name: str, index: int = 0,
                         partial: bool = True) -> dict:
    """Right-click the Nth control matching a ClassName."""
    try:
        matches = driver.find_by_class(class_name, partial=partial)
        if not matches:
            return _fail(_hint_no_control(driver, class_name, "class"))
        if index >= len(matches):
            return _fail(f"Only {len(matches)} controls with class '{class_name}', wanted index {index}")
        ctrl = matches[index]
        info = driver._get_control_info(ctrl)
        driver.right_click_control(ctrl)
        return _ok(f"Right-clicked '{info['name']}' ({info['class']})", {"control": info})
    except Exception as e:
        return _fail(f"Failed to right-click: {e}")


def hover_by_name(driver: AppDriver, name: str, partial: bool = True) -> dict:
    """Hover (move mouse to) a control found by Name."""
    try:
        matches = driver.find_by_name(name, partial=partial)
        if not matches:
            return _fail(_hint_no_control(driver, name, "name"))
        ctrl = matches[0]
        info = driver._get_control_info(ctrl)
        driver.hover_control(ctrl)
        return _ok(f"Hovering over '{info['name']}' ({info['class']})", {"control": info})
    except Exception as e:
        return _fail(f"Failed to hover '{name}': {e}")


def hover_by_class(driver: AppDriver, class_name: str, index: int = 0,
                   partial: bool = True) -> dict:
    """Hover (move mouse to) the Nth control matching a ClassName."""
    try:
        matches = driver.find_by_class(class_name, partial=partial)
        if not matches:
            return _fail(_hint_no_control(driver, class_name, "class"))
        if index >= len(matches):
            return _fail(f"Only {len(matches)} controls with class '{class_name}', wanted index {index}")
        ctrl = matches[index]
        info = driver._get_control_info(ctrl)
        driver.hover_control(ctrl)
        return _ok(f"Hovering over '{info['name']}' ({info['class']})", {"control": info})
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
        return _ok(f"Sent key '{key}'")
    except Exception as e:
        return _fail(f"Failed to send key '{key}': {e}")


def send_hotkey(driver: AppDriver, keys: str) -> dict:
    """Send a key combination. E.g. 'Ctrl+c', 'Alt+F4', 'Ctrl+Shift+s'."""
    try:
        parts = [k.strip() for k in keys.split("+")]
        driver.send_hotkey(*parts)
        return _ok(f"Sent hotkey '{keys}'")
    except Exception as e:
        return _fail(f"Failed to send hotkey '{keys}': {e}")


def long_press_key(driver: AppDriver, key: str, duration: float = 1.0) -> dict:
    """Hold a key down for duration seconds, then release."""
    try:
        driver.long_press_key(key, duration)
        return _ok(f"Long-pressed '{key}' for {duration}s")
    except Exception as e:
        return _fail(f"Failed to long-press '{key}': {e}")


def list_windows(driver: AppDriver) -> dict:
    """List all top-level windows on the desktop."""
    try:
        import uiautomation as auto
        windows = []
        for ctrl in auto.GetRootControl().GetChildren():
            if ctrl.ControlTypeName == "WindowControl":
                info = driver._get_control_info(ctrl)
                info["handle"] = ctrl.NativeWindowHandle
                windows.append(info)
        return _ok(f"Found {len(windows)} windows", {"windows": windows})
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
