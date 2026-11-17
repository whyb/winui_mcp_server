import unittest
from unittest.mock import Mock, patch

from winui_mcp import driver
from winui_mcp import skills_library as sk
from winui_mcp.driver import AppDriver


class _Rect:
    def __init__(self, left, top, right=100, bottom=80):
        self.left = left
        self.top = top
        self.right = right
        self.bottom = bottom

    def width(self):
        return self.right - self.left

    def height(self):
        return self.bottom - self.top


def _bare_driver(rect):
    app = AppDriver.__new__(AppDriver)
    app._window = Mock()
    app._window.BoundingRectangle = rect
    app._hwnd = 0x1234
    app._pid = 1234
    app.move_window_by_mouse = Mock(
        return_value=(rect.left, rect.top, rect.left, rect.top)
    )
    app.move_window = Mock(
        return_value=(rect.left, rect.top, rect.left, rect.top)
    )
    return app


class MoveWindowSkillTests(unittest.TestCase):
    def test_mouse_drag_returns_moved_state(self):
        rect = _Rect(100, 120)
        app = _bare_driver(rect)

        def drag(dx, dy):
            app._window.BoundingRectangle = _Rect(160, 150)

        app.move_window_by_mouse = Mock(side_effect=drag)
        with patch.object(driver.time, "sleep", return_value=None):
            result = sk.move_window(app, delta_x=60, delta_y=30, method="mouse")
        self.assertTrue(result["success"])
        self.assertTrue(result["verified"])
        self.assertEqual(result["data"]["method"], "mouse")
        self.assertEqual(result["data"]["to"], {"left": 160, "top": 150})
        self.assertEqual(result["data"]["delta"], {"x": 60, "y": 30})
        app.move_window_by_mouse.assert_called_once_with(60, 30)

    def test_mouse_drag_reports_unverified_when_position_unchanged(self):
        app = _bare_driver(_Rect(100, 120))
        result = sk.move_window(app, delta_x=0, delta_y=0, method="mouse")
        self.assertTrue(result["success"])
        self.assertFalse(result["verified"])
        self.assertEqual(result["data"]["delta"], {"x": 0, "y": 0})

    def test_setwindowpos_requires_absolute_coordinates(self):
        app = _bare_driver(_Rect(100, 120))
        result = sk.move_window(app, method="setwindowpos")
        self.assertFalse(result["success"])
        self.assertIn("absolute", result["message"])

    def test_setwindowpos_uses_absolute_target(self):
        rect = _Rect(100, 120)
        app = _bare_driver(rect)

        def move(x, y):
            app._window.BoundingRectangle = _Rect(x, y)

        app.move_window = Mock(side_effect=move)
        with patch.object(driver.time, "sleep", return_value=None):
            result = sk.move_window(app, x=400, y=300, method="setwindowpos")
        self.assertTrue(result["success"])
        self.assertTrue(result["verified"])
        app.move_window.assert_called_once_with(400, 300)

    def test_unknown_method_is_rejected(self):
        app = _bare_driver(_Rect(100, 120))
        result = sk.move_window(app, method="teleport")
        self.assertFalse(result["success"])
        app.move_window_by_mouse.assert_not_called()
        app.move_window.assert_not_called()

    def test_driver_mouse_drag_uses_title_bar_point(self):
        rect = _Rect(100, 120, right=300, bottom=200)
        app = AppDriver.__new__(AppDriver)
        app._window = Mock()
        app._window.BoundingRectangle = rect
        app._hwnd = 0x1234
        app._pid = 1234
        with patch.object(driver, "_mouse_drag") as drag:
            result = app.move_window_by_mouse(delta_x=40, delta_y=25)
        self.assertEqual(result, (100, 120, 100, 120))
        drag.assert_called_once_with(200, 128, 240, 153)

    def test_driver_setwindowpos_uses_native_handle(self):
        rect = _Rect(100, 120, right=300, bottom=200)
        app = AppDriver.__new__(AppDriver)
        app._window = Mock()
        app._window.BoundingRectangle = rect
        app._hwnd = 0x1234
        app._pid = 1234
        with patch.object(driver, "_get_native_handle", return_value=0xABC), \
             patch.object(driver._user32, "SetWindowPos", return_value=1) as set_pos, \
             patch.object(driver.time, "sleep", return_value=None):
            result = app.move_window(50, 60)
        self.assertEqual(set_pos.call_args.args[0], 0xABC)
        self.assertEqual(set_pos.call_args.args[2:4], (50, 60))
        self.assertEqual(result, (100, 120, 100, 120))

    def test_driver_setwindowpos_raises_without_handle(self):
        app = AppDriver.__new__(AppDriver)
        app._window = Mock()
        app._window.BoundingRectangle = _Rect(100, 120)
        app._hwnd = 0x1234
        app._pid = 1234
        with patch.object(driver, "_get_native_handle", return_value=0):
            with self.assertRaises(RuntimeError):
                app.move_window(50, 60)


if __name__ == "__main__":
    unittest.main()
