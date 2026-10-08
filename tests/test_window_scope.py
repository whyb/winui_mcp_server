import unittest
from unittest.mock import patch

from winui_mcp import driver
from winui_mcp.driver import AppDriver


class _Control:
    def __init__(self, name="", class_name="Control", handle=0, children=None):
        self.Name = name
        self.ClassName = class_name
        self.NativeWindowHandle = handle
        self.ControlTypeName = "WindowControl" if class_name == "WindowControl" else "ButtonControl"
        self._children = children or []
        self.clicked = False

    def GetChildren(self):
        return self._children

    def Exists(self, maxSearchSeconds=0):
        return True

    def Click(self):
        self.clicked = True


class _Root:
    def __init__(self, children):
        self._children = children

    def GetChildren(self):
        return self._children


class WindowScopeTests(unittest.TestCase):
    def _driver(self, main):
        app = AppDriver.__new__(AppDriver)
        app._window = main
        app._pid = 100
        app._hwnd = main.NativeWindowHandle
        app._window_title = "App"
        app._window_class = None
        app._process_name = None
        app._timeout = 5
        return app

    def test_find_by_name_searches_popup_windows(self):
        popup_button = _Control(name="PopupButton")
        main = _Control(class_name="WindowControl", handle=10)
        popup = _Control(class_name="WindowControl", handle=11, children=[popup_button])
        other = _Control(class_name="WindowControl", handle=12)
        app = self._driver(main)

        with patch.object(driver.auto, "GetRootControl", return_value=_Root([main, popup, other])), \
             patch.object(driver, "_get_pid_from_hwnd", side_effect=lambda hwnd: 100 if hwnd in (10, 11) else 200):
            self.assertEqual(app.find_by_name("PopupButton", partial=False), [popup_button])

    def test_click_control_does_not_force_main_window_focus(self):
        button = _Control(name="OK")
        app = self._driver(_Control(class_name="WindowControl", handle=10))
        app.focus = lambda: (_ for _ in ()).throw(AssertionError("focus should not be called"))

        app.click_control(button)

        self.assertTrue(button.clicked)

    def test_keyboard_focus_keeps_same_process_popup(self):
        popup = _Control(class_name="WindowControl", handle=11)
        foreground = _Control(name="Edited", handle=0)
        foreground.GetTopLevelControl = lambda: popup
        app = self._driver(_Control(class_name="WindowControl", handle=10))
        app.focus = lambda: (_ for _ in ()).throw(AssertionError("focus should not be called"))

        with patch.object(driver.auto, "GetForegroundControl", return_value=foreground), \
             patch.object(driver, "_get_pid_from_hwnd", return_value=100):
            app._ensure_process_foreground()

    def test_keyboard_focus_returns_to_app_when_other_process_is_active(self):
        main = _Control(class_name="WindowControl", handle=10)
        other = _Control(class_name="WindowControl", handle=12)
        foreground = _Control(name="Other", handle=0)
        foreground.GetTopLevelControl = lambda: other
        app = self._driver(main)
        focused = []
        app.focus = lambda: focused.append(True)

        with patch.object(driver.auto, "GetForegroundControl", return_value=foreground), \
             patch.object(driver, "_get_pid_from_hwnd", side_effect=lambda hwnd: 100 if hwnd == 10 else 200):
            app._ensure_process_foreground()

        self.assertEqual(focused, [True])


if __name__ == "__main__":
    unittest.main()
