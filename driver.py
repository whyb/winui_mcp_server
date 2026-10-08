"""
driver.py - Core window binding, focus control, and UIA element resolution.
Generic engine that works with any Windows application.
"""
import time
import ctypes
import ctypes.wintypes
import uiautomation as auto


# ── DPI Awareness ──
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)  # Per-monitor DPI aware
except Exception:
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass


def _get_class_name(control: auto.Control) -> str:
    try:
        return control.ClassName or ""
    except Exception:
        return ""


def _get_name(control: auto.Control) -> str:
    try:
        return control.Name or ""
    except Exception:
        return ""


def _get_pid_from_hwnd(hwnd: int) -> int:
    pid = ctypes.wintypes.DWORD()
    ctypes.windll.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    return pid.value


def _get_process_name(pid: int) -> str:
    PROCESS_QUERY_INFORMATION = 0x0400
    PROCESS_VM_READ = 0x0010
    h = ctypes.windll.kernel32.OpenProcess(
        PROCESS_QUERY_INFORMATION | PROCESS_VM_READ, False, pid
    )
    if not h:
        return ""
    try:
        buf = ctypes.create_unicode_buffer(512)
        size = ctypes.wintypes.DWORD(512)
        ctypes.windll.psapi.GetModuleBaseNameW(h, None, buf, size)
        return buf.value
    finally:
        ctypes.windll.kernel32.CloseHandle(h)


def _get_native_handle(control: auto.Control) -> int:
    """Return a control or window native handle, or zero if unavailable."""
    try:
        return int(control.NativeWindowHandle or 0)
    except Exception:
        return 0


def _get_control_pid(control: auto.Control) -> int:
    """Best-effort process id for a UIA control."""
    hwnd = _get_native_handle(control)
    if hwnd:
        return _get_pid_from_hwnd(hwnd)
    try:
        top = control.GetTopLevelControl()
        hwnd = _get_native_handle(top)
        return _get_pid_from_hwnd(hwnd) if hwnd else 0
    except Exception:
        return 0


def _find_window_by_title(title: str, class_name: str = None,
                          timeout: float = 5, fuzzy: bool = True) -> auto.WindowControl:
    """
    Find a window by title.
    1. Try exact match via uiautomation Name=
    2. If fuzzy=True, fall back to substring match on all top-level windows
    """
    # Exact match
    kwargs = {"searchDepth": 1, "Name": title}
    if class_name:
        kwargs["ClassName"] = class_name
    window = auto.WindowControl(**kwargs)
    if window.Exists(maxSearchSeconds=timeout):
        return window

    if not fuzzy:
        raise RuntimeError(
            f"Window with exact title '{title}' not found within {timeout}s."
        )

    # Fuzzy: substring match on all top-level windows
    title_lower = title.lower()
    for ctrl in auto.GetRootControl().GetChildren():
        if ctrl.ControlTypeName != "WindowControl":
            continue
        name = _get_name(ctrl)
        if name and title_lower in name.lower():
            if class_name:
                if _get_class_name(ctrl) != class_name:
                    continue
            return ctrl

    raise RuntimeError(
        f"Window matching '{title}' not found (tried exact + fuzzy). "
        "Is the application running?"
    )


def _find_window_by_process(process_name: str, timeout: float = 5) -> auto.WindowControl:
    """Find the first visible top-level window belonging to a process name."""
    import time as _time
    deadline = _time.time() + timeout
    proc_lower = process_name.lower()
    if not proc_lower.endswith(".exe"):
        proc_lower += ".exe"

    while _time.time() < deadline:
        for ctrl in auto.GetRootControl().GetChildren():
            if ctrl.ControlTypeName != "WindowControl":
                continue
            try:
                hwnd = ctrl.NativeWindowHandle
                pid = _get_pid_from_hwnd(hwnd)
                pname = _get_process_name(pid)
                if pname and pname.lower() == proc_lower:
                    return ctrl
            except Exception:
                continue
        _time.sleep(0.5)

    raise RuntimeError(
        f"No window found for process '{process_name}' within {timeout}s. "
        "Is the application running?"
    )


def resolve_locator(window: auto.WindowControl, locator: tuple) -> auto.Control:
    """
    Resolve a hierarchical locator tuple to a UIA control.

    Locator elements:
      - "ClassName"      : find first direct child with that ClassName
      - "ClassName@N"    : find Nth (0-based) direct child with that ClassName
      - int              : select child at this index among all direct children
    """
    if not locator:
        raise ValueError("Empty locator")

    current = window

    for elem in locator:
        if isinstance(elem, str):
            if "@" in elem:
                class_name, idx_str = elem.rsplit("@", 1)
                idx = int(idx_str)
                children = current.GetChildren()
                matches = [c for c in children if _get_class_name(c) == class_name]
                if idx >= len(matches):
                    raise LookupError(
                        f"Only {len(matches)} children with ClassName='{class_name}' "
                        f"under '{_get_class_name(current)}', wanted index {idx}"
                    )
                current = matches[idx]
            else:
                children = current.GetChildren()
                matches = [c for c in children if _get_class_name(c) == elem]
                if not matches:
                    raise LookupError(
                        f"No child with ClassName='{elem}' found under "
                        f"'{_get_class_name(current)}' (Name='{_get_name(current)}')"
                    )
                current = matches[0]
        elif isinstance(elem, int):
            children = current.GetChildren()
            if elem >= len(children):
                raise IndexError(
                    f"Index {elem} out of range (have {len(children)} children) "
                    f"under '{_get_class_name(current)}'"
                )
            current = children[elem]
        else:
            raise TypeError(f"Invalid locator element: {elem!r}")

    return current


def resolve_locator_safe(window: auto.WindowControl, locator: tuple,
                         timeout: float = 5) -> auto.Control:
    """Resolve locator with retry/timeout."""
    deadline = time.time() + timeout
    last_err = None
    while time.time() < deadline:
        try:
            return resolve_locator(window, locator)
        except (LookupError, IndexError) as e:
            last_err = e
            time.sleep(0.3)
    raise TimeoutError(
        f"Could not resolve locator {locator} within {timeout}s: {last_err}"
    )


def get_all_children_by_class(control: auto.Control, class_name: str) -> list:
    """Get all direct children matching a ClassName."""
    return [c for c in control.GetChildren() if _get_class_name(c) == class_name]


def _read_value(control: auto.Control):
    """Read a ValuePattern value, or None when the pattern is unavailable."""
    try:
        return control.GetValuePattern().Value
    except Exception:
        return None


def _read_toggle_state(control: auto.Control):
    """Read a TogglePattern state. Returns True/False, or None if unknown."""
    try:
        state = control.GetTogglePattern().ToggleState
        if state == 2:
            return None
        return state == 1
    except Exception:
        return None


def _read_selected_names(control: auto.Control):
    """Read selected item names, falling back to the control value."""
    try:
        selected = control.GetSelectionPattern().GetSelection()
        return [_get_name(item) for item in selected]
    except Exception:
        pass
    value = _read_value(control)
    if value is not None:
        return [value]
    return None


def _selection_matches_text(control: auto.Control, text: str):
    """Return whether the current selection matches text, or None if unknown."""
    names = _read_selected_names(control)
    if names is None:
        return None
    wanted = text.casefold()
    return any(wanted in name.casefold() for name in names)


class AppDriver:
    """High-level driver wrapping window binding and element resolution.
    Works with any Windows application — pass window_title, process_name, or both."""

    def __init__(self, window_title: str = None, window_class: str = None,
                 process_name: str = None, timeout: int = 5):
        self._window_title = window_title
        self._window_class = window_class
        self._process_name = process_name
        self._window = None
        self._pid = 0
        self._hwnd = 0
        self._timeout = timeout

    def find_main_window(self) -> auto.WindowControl:
        """Find and return the main application window.
        Priority: process_name > window_title (exact then fuzzy)."""
        if self._process_name:
            return _find_window_by_process(self._process_name, timeout=self._timeout)
        if self._window_title:
            return _find_window_by_title(
                self._window_title, self._window_class,
                timeout=self._timeout, fuzzy=True
            )
        raise RuntimeError("No window_title or process_name specified.")

    def _remember_window(self, window: auto.WindowControl) -> None:
        """Record the concrete window identity used by this driver."""
        self._window = window
        self._pid = _get_control_pid(window)
        self._hwnd = _get_native_handle(window)

    @property
    def window(self) -> auto.WindowControl:
        """Return the originally bound window; never silently retarget."""
        if self._window is None:
            self._remember_window(self.find_main_window())
            return self._window
        if not self._window.Exists(maxSearchSeconds=1):
            raise RuntimeError(
                "Bound window no longer exists; call reset_driver before retrying"
            )
        current_pid = _get_control_pid(self._window)
        if self._pid and current_pid and current_pid != self._pid:
            raise RuntimeError(
                "Bound window handle now belongs to another process; "
                "call reset_driver before retrying"
            )
        if not self._hwnd:
            self._hwnd = _get_native_handle(self._window)
        return self._window

    def window_identity(self) -> tuple:
        """Return the stable identity for the currently bound window."""
        return (self._pid, self._hwnd)

    def get_search_roots(self) -> list:
        """Return the main window and all same-process top-level surfaces."""
        main = self.window
        if not self._pid:
            self._pid = _get_control_pid(main)
        roots = [main]
        seen = {_get_native_handle(main)}
        try:
            top_level = auto.GetRootControl().GetChildren()
        except Exception:
            return roots

        for control in top_level:
            try:
                if control.ControlTypeName != "WindowControl":
                    continue
                handle = _get_native_handle(control)
                if not handle or handle in seen:
                    continue
                if _get_pid_from_hwnd(handle) != self._pid:
                    continue
                roots.append(control)
                seen.add(handle)
            except Exception:
                continue
        return roots

    def get_foreground_window(self):
        """Return the current foreground top-level window when it belongs to this app."""
        try:
            foreground = auto.GetForegroundControl()
            if foreground is None:
                return None
            top_level = foreground.GetTopLevelControl() or foreground
            if _get_control_pid(top_level) == self._pid:
                return top_level
        except Exception:
            pass
        return None

    def _ensure_process_foreground(self) -> None:
        """Keep a same-process dialog/popup active; otherwise focus the main window."""
        if self.get_foreground_window() is None:
            self.focus()

    def focus(self) -> None:
        """Ensure the app window is in the foreground."""
        win = self.window
        try:
            if win.IsMinimize():
                win.Restore()
                time.sleep(0.3)
            win.SetFocus()
            time.sleep(0.1)
        except Exception:
            try:
                hwnd = win.NativeWindowHandle
                ctypes.windll.user32.ShowWindow(hwnd, 9)  # SW_RESTORE
                ctypes.windll.user32.SetForegroundWindow(hwnd)
                time.sleep(0.2)
            except Exception:
                pass

    def resolve(self, locator: tuple, timeout: float = None) -> auto.Control:
        """Resolve a locator tuple to a live UIA control."""
        t = timeout if timeout is not None else self._timeout
        return resolve_locator_safe(self.window, locator, t)

    def click(self, locator: tuple, timeout: float = None) -> None:
        """Click a control identified by locator."""
        ctrl = self.resolve(locator, timeout)
        ctrl.Click()
        time.sleep(0.2)

    def invoke(self, locator: tuple, timeout: float = None) -> None:
        """Invoke a control (for buttons that support InvokePattern)."""
        ctrl = self.resolve(locator, timeout)
        try:
            pattern = ctrl.GetInvokePattern()
            pattern.Invoke()
        except Exception:
            ctrl.Click()
        time.sleep(0.2)

    def set_value(self, locator: tuple, value: str, timeout: float = None):
        """Set an edit control value and return verification state."""
        ctrl = self.resolve(locator, timeout)
        return self.set_value_by_control(ctrl, value)

    def set_value_by_control(self, ctrl: auto.Control, value: str):
        """Set a control value. Returns True/False, or None if unverifiable."""
        try:
            ctrl.GetValuePattern().SetValue(value)
        except Exception:
            ctrl.Click()
            time.sleep(0.1)
            ctrl.SendKeys("{Ctrl}a")
            time.sleep(0.05)
            ctrl.SendKeys(value)
        time.sleep(0.2)
        actual = _read_value(ctrl)
        if actual is None:
            return None
        return actual == value

    def get_value(self, locator: tuple, timeout: float = None) -> str:
        """Get the current value of an edit/combo control."""
        ctrl = self.resolve(locator, timeout)
        actual = _read_value(ctrl)
        return _get_name(ctrl) if actual is None else actual

    def select_combobox_item(self, locator: tuple, item_text: str,
                             timeout: float = None):
        """
        Open a combobox and select an item by text.
        Returns True when verified, False when selection is known not to match,
        and None when the app does not expose a readable selection state.
        """
        ctrl = self.resolve(locator, timeout)
        return self.select_combobox_item_by_control(ctrl, item_text)

    def select_combobox_item_by_control(self, ctrl: auto.Control, item_text: str):
        """Select and verify a combobox item on an already resolved control."""
        ctrl.Click()
        time.sleep(0.5)

        try:
            ctrl.GetExpandCollapsePattern().Expand()
            time.sleep(0.3)
        except Exception:
            pass

        for item in ctrl.GetChildren():
            if item_text.casefold() in _get_name(item).casefold():
                item.Click()
                time.sleep(0.3)
                return self._verify_combobox_selection(ctrl, item_text)
            try:
                for sub in item.GetChildren():
                    if item_text.casefold() in _get_name(sub).casefold():
                        sub.Click()
                        time.sleep(0.3)
                        return self._verify_combobox_selection(ctrl, item_text)
            except Exception:
                pass

        try:
            ctrl.GetExpandCollapsePattern().Collapse()
        except Exception:
            ctrl.Click()
        return False

    @staticmethod
    def _verify_combobox_selection(ctrl: auto.Control, item_text: str):
        """Poll the readable selection state briefly after selecting an item."""
        state = None
        for _ in range(5):
            state = _selection_matches_text(ctrl, item_text)
            if state is True:
                return True
            time.sleep(0.1)
        return state

    def toggle_checkbox(self, locator: tuple, desired_state: bool = True,
                        timeout: float = None):
        """Toggle a checkbox to the desired state (True=checked)."""
        ctrl = self.resolve(locator, timeout)
        return self.toggle_checkbox_by_control(ctrl, desired_state)

    def toggle_checkbox_by_control(self, ctrl: auto.Control,
                                   desired_state: bool = True):
        """Set a checkbox state. Returns True/False, or None if unverifiable."""
        desired_state = bool(desired_state)
        try:
            pattern = ctrl.GetTogglePattern()
            for _ in range(4):
                if _read_toggle_state(ctrl) == desired_state:
                    return True
                pattern.Toggle()
                time.sleep(0.1)
            return _read_toggle_state(ctrl) == desired_state
        except Exception:
            ctrl.Click()
            time.sleep(0.3)
            return _read_toggle_state(ctrl)

    def is_checked(self, locator: tuple, timeout: float = None):
        """Return True/False for a checkbox state, or None if unknown."""
        ctrl = self.resolve(locator, timeout)
        return _read_toggle_state(ctrl)

    def scroll_to(self, sidebar_path: tuple, section_class: str) -> None:
        """Scroll a sidebar/scroll area to make a section visible.
        sidebar_path: locator tuple to the content QWidget (e.g. ("MyWidget", "CScrollArea", 0, "QWidget"))
        section_class: ClassName of the section to scroll to
        """
        try:
            section = self.resolve((*sidebar_path, section_class), timeout=3)
            section.ScrollIntoView()
            time.sleep(0.3)
        except Exception:
            pass

    # ── Dynamic UIA Discovery ──

    @staticmethod
    def _get_control_info(control: auto.Control) -> dict:
        """Extract info dict from a UIA control."""
        info = {
            "class": _get_class_name(control),
            "name": _get_name(control),
        }
        try:
            info["auto_id"] = control.AutomationId or ""
        except Exception:
            info["auto_id"] = ""
        try:
            info["control_type"] = control.ControlTypeName or ""
        except Exception:
            info["control_type"] = ""
        try:
            rect = control.BoundingRectangle
            info["rect"] = {
                "left": rect.left, "top": rect.top,
                "right": rect.right, "bottom": rect.bottom,
                "width": rect.width(), "height": rect.height(),
            }
            info["visible"] = rect.width() > 0 and rect.height() > 0
        except Exception:
            info["rect"] = None
            info["visible"] = False
        # Detect supported patterns
        patterns = []
        for pname in ("Value", "Toggle", "Invoke", "ExpandCollapse",
                       "ScrollItem", "Selection", "RangeValue"):
            try:
                getattr(control, f"Get{pname}Pattern")()
                patterns.append(pname)
            except Exception:
                pass
        info["patterns"] = patterns
        return info

    def describe_children(self, control: auto.Control = None, depth: int = 1) -> list:
        """List children of a control with their attributes.
        If control is None, uses the main window."""
        if control is None:
            control = self.window
        result = []
        for i, child in enumerate(control.GetChildren()):
            info = self._get_control_info(child)
            info["index"] = i
            if depth > 1:
                info["children"] = self.describe_children(child, depth - 1)
            result.append(info)
        return result

    def dump_tree(self, control: auto.Control = None, max_depth: int = 3,
                  _depth: int = 0) -> dict:
        """Recursively dump UIA tree structure."""
        if control is None:
            control = self.window
        info = self._get_control_info(control)
        info["depth"] = _depth
        if _depth < max_depth:
            children = []
            for child in control.GetChildren():
                children.append(self.dump_tree(child, max_depth, _depth + 1))
            info["children"] = children
        else:
            info["child_count"] = len(control.GetChildren())
        return info

    def find_by_name(self, name: str, control: auto.Control = None,
                     partial: bool = False) -> list:
        """Find controls by Name attribute (searches all descendants).
        partial=True for substring match. Exact matches always come first."""
        if control is None:
            exact = []
            fuzzy = []
            for root in self.get_search_roots():
                root_exact, root_fuzzy = self._find_by_name_split(name, root, partial)
                exact.extend(root_exact)
                fuzzy.extend(root_fuzzy)
            return exact + fuzzy
        exact = []
        fuzzy = []
        try:
            for child in control.GetChildren():
                child_name = _get_name(child)
                if child_name == name:
                    exact.append(child)
                elif partial and name.lower() in child_name.lower():
                    fuzzy.append(child)
                child_exact, child_fuzzy = self._find_by_name_split(
                    name, child, partial)
                exact.extend(child_exact)
                fuzzy.extend(child_fuzzy)
        except Exception:
            pass
        return exact + fuzzy

    def _find_by_name_split(self, name: str, control: auto.Control,
                            partial: bool) -> tuple:
        """Internal: return (exact_matches, fuzzy_matches) separately."""
        if control is None:
            return ([], [])
        exact = []
        fuzzy = []
        try:
            for child in control.GetChildren():
                child_name = _get_name(child)
                if child_name == name:
                    exact.append(child)
                elif partial and name.lower() in child_name.lower():
                    fuzzy.append(child)
                child_exact, child_fuzzy = self._find_by_name_split(
                    name, child, partial)
                exact.extend(child_exact)
                fuzzy.extend(child_fuzzy)
        except Exception:
            pass
        return (exact, fuzzy)

    def find_by_class(self, class_name: str, control: auto.Control = None,
                      partial: bool = False) -> list:
        """Find controls by ClassName (searches all descendants).
        Exact matches always come first."""
        if control is None:
            exact = []
            fuzzy = []
            for root in self.get_search_roots():
                root_exact, root_fuzzy = self._find_by_class_split(class_name, root, partial)
                exact.extend(root_exact)
                fuzzy.extend(root_fuzzy)
            return exact + fuzzy
        exact = []
        fuzzy = []
        try:
            for child in control.GetChildren():
                child_class = _get_class_name(child)
                if child_class == class_name:
                    exact.append(child)
                elif partial and class_name.lower() in child_class.lower():
                    fuzzy.append(child)
                child_exact, child_fuzzy = self._find_by_class_split(
                    class_name, child, partial)
                exact.extend(child_exact)
                fuzzy.extend(child_fuzzy)
        except Exception:
            pass
        return exact + fuzzy

    def _find_by_class_split(self, class_name: str, control: auto.Control,
                             partial: bool) -> tuple:
        """Internal: return (exact_matches, fuzzy_matches) separately."""
        if control is None:
            return ([], [])
        exact = []
        fuzzy = []
        try:
            for child in control.GetChildren():
                child_class = _get_class_name(child)
                if child_class == class_name:
                    exact.append(child)
                elif partial and class_name.lower() in child_class.lower():
                    fuzzy.append(child)
                child_exact, child_fuzzy = self._find_by_class_split(
                    class_name, child, partial)
                exact.extend(child_exact)
                fuzzy.extend(child_fuzzy)
        except Exception:
            pass
        return (exact, fuzzy)

    def find_by_auto_id(self, auto_id: str, control: auto.Control = None) -> list:
        """Find controls by AutomationId (searches all descendants)."""
        if control is None:
            results = []
            for root in self.get_search_roots():
                results.extend(self.find_by_auto_id(auto_id, root))
            return results
        results = []
        try:
            for child in control.GetChildren():
                try:
                    if (child.AutomationId or "") == auto_id:
                        results.append(child)
                except Exception:
                    pass
                results.extend(self.find_by_auto_id(auto_id, child))
        except Exception:
            pass
        return results

    def click_control(self, control: auto.Control) -> None:
        """Click a UIA control directly."""
        control.Click()
        time.sleep(0.2)

    def type_text(self, text: str, control: auto.Control = None) -> None:
        """Type text into a control (or the focused element if control is None)."""
        if control is not None:
            control.Click()
            time.sleep(0.1)
            try:
                control.SetFocus()
            except Exception:
                pass
        else:
            self._ensure_process_foreground()
        auto.SendKeys(text)
        time.sleep(0.2)

    def double_click_control(self, control: auto.Control) -> None:
        """Double-click a UIA control directly."""
        control.DoubleClick()
        time.sleep(0.2)

    def right_click_control(self, control: auto.Control) -> None:
        """Right-click a UIA control directly."""
        control.RightClick()
        time.sleep(0.2)

    def hover_control(self, control: auto.Control) -> None:
        """Hover (move mouse to) a UIA control."""
        control.MoveCursorToMyCenter()
        time.sleep(0.1)

    def scroll_up(self, control: auto.Control = None, count: int = 3) -> None:
        """Scroll up on a control or the window."""
        self._ensure_process_foreground()
        target = control if control is not None else self.window
        for _ in range(count):
            target.WheelUp()
            time.sleep(0.05)
        time.sleep(0.2)

    def scroll_down(self, control: auto.Control = None, count: int = 3) -> None:
        """Scroll down on a control or the window."""
        self._ensure_process_foreground()
        target = control if control is not None else self.window
        for _ in range(count):
            target.WheelDown()
            time.sleep(0.05)
        time.sleep(0.2)

    def send_key(self, key: str) -> None:
        """Send a single key press. E.g. '{Enter}', '{Escape}', '{Tab}', 'a'."""
        self._ensure_process_foreground()
        auto.SendKeys(key)
        time.sleep(0.1)

    def send_hotkey(self, *keys: str) -> None:
        """Send a key combination. E.g. ('Ctrl', 'c'), ('Alt', 'F4')."""
        self._ensure_process_foreground()
        combo = "".join(f"{{{k}}}" if len(k) > 1 else k for k in keys)
        auto.SendKeys(combo)
        time.sleep(0.1)

    def long_press_key(self, key: str, duration: float = 1.0) -> None:
        """Hold a key down for duration seconds, then release."""
        self._ensure_process_foreground()
        vk = auto.CharToKeyCode(key)
        ctypes.windll.user32.keybd_event(vk, 0, 0, 0)  # key down
        time.sleep(duration)
        ctypes.windll.user32.keybd_event(vk, 0, 2, 0)  # key up (KEYEVENTF_KEYUP)
        time.sleep(0.1)


# ── Driver Cache ──

_driver_cache: dict = {}


def get_cached_driver(window_title: str = None, process_name: str = None,
                      window_class: str = None, timeout: int = 5) -> AppDriver:
    """Get or create a cached AppDriver. Avoids repeated window lookups."""
    key = (window_title, process_name, window_class)
    cached = _driver_cache.get(key)
    if cached is not None:
        try:
            _ = cached.window
            return cached
        except Exception as e:
            raise RuntimeError(
                f"Cached window binding is no longer valid: {e}. "
                "Call reset_driver before retrying."
            ) from e

    driver = AppDriver(
        window_title=window_title,
        process_name=process_name,
        window_class=window_class,
        timeout=timeout,
    )
    _ = driver.window
    _driver_cache[key] = driver
    return driver


def clear_driver_cache() -> None:
    """Clear all cached drivers."""
    _driver_cache.clear()
