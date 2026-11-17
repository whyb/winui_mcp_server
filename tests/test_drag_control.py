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


class DragControlSkillTests(unittest.TestCase):
    def test_drag_by_element_id_returns_moved_state(self):
        app = AppDriver.__new__(AppDriver)
        app._get_control_info = lambda control: {
            "name": "Vertical Scroll Bar", "class": "ScrollBar",
        }
        ctrl = Mock()
        ctrl.BoundingRectangle = _Rect(480, 200, 500, 400)

        def drag_and_move(control, delta_x, delta_y):
            ctrl.BoundingRectangle = _Rect(480, 260, 500, 460)
            return (490, 300, 490, 360)

        app.drag_control = Mock(side_effect=drag_and_move)
        app.resolve_element = Mock(return_value=ctrl)

        result = sk.drag_control(app, delta_x=0, delta_y=60, element_id="e7")

        self.assertTrue(result["success"])
        self.assertTrue(result["verified"])
        self.assertEqual(result["data"]["delta"], {"x": 0, "y": 60})
        app.resolve_element.assert_called_once_with("e7")
        args = app.drag_control.call_args.args
        self.assertIs(args[0], ctrl)
        self.assertEqual(args[1:], (0, 60))

    def test_drag_reports_unverified_when_control_does_not_move(self):
        app = AppDriver.__new__(AppDriver)
        app._get_control_info = lambda control: {"name": "Thumb", "class": "Thumb"}
        ctrl = Mock()
        ctrl.BoundingRectangle = _Rect(480, 200, 500, 400)
        app.drag_control = Mock(return_value=(490, 300, 490, 300))
        app.resolve_element = Mock(return_value=ctrl)

        result = sk.drag_control(app, delta_x=10, delta_y=0, element_id="e3")

        self.assertTrue(result["success"])
        self.assertFalse(result["verified"])

    def test_drag_missing_target_fails(self):
        app = AppDriver.__new__(AppDriver)
        app.resolve_element = Mock(side_effect=LookupError("stale element id"))

        result = sk.drag_control(app, delta_x=1, delta_y=1, element_id="e9")

        self.assertFalse(result["success"])
        self.assertIn("stale", result["message"])

    def test_drag_without_target_fails(self):
        app = AppDriver.__new__(AppDriver)
        result = sk.drag_control(app, delta_x=1, delta_y=1)
        self.assertFalse(result["success"])

    def test_driver_drag_uses_control_center(self):
        rect = _Rect(480, 200, right=500, bottom=400)
        ctrl = Mock()
        ctrl.BoundingRectangle = rect
        app = AppDriver.__new__(AppDriver)
        with patch.object(driver, "_mouse_drag") as drag:
            result = app.drag_control(ctrl, delta_x=0, delta_y=80)
        drag.assert_called_once_with(490, 300, 490, 380)
        self.assertEqual(result, (490, 300, 490, 300))

    def test_mouse_drag_releases_button_on_error(self):
        attempts = []

        def cursor(x, y):
            attempts.append((x, y))
            if len(attempts) > 1:
                raise RuntimeError("drag failed")

        with patch.object(driver.auto, "SetCursorPos", side_effect=cursor), \
             patch.object(driver.auto, "PressMouse") as press, \
             patch.object(driver.auto, "ReleaseMouse") as release, \
             patch.object(driver.time, "sleep", return_value=None):
            with self.assertRaises(RuntimeError):
                driver._mouse_drag(10, 10, 20, 20)
        press.assert_called_once()
        release.assert_called_once()


if __name__ == "__main__":
    unittest.main()
