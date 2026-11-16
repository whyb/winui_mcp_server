import unittest
from unittest.mock import patch

from winui_mcp import skills_library as sk


class _Root:
    def GetChildren(self):
        return []


class _Driver:
    def _get_control_info(self, control, detailed=True):
        return {
            "class": getattr(control, "ClassName", ""),
            "name": getattr(control, "Name", ""),
            "auto_id": "",
            "control_type": getattr(control, "ControlTypeName", ""),
            "enabled": True,
            "visible": True,
            "offscreen": False,
            "patterns": [],
            "interactive": False,
            "rect": {"width": 100, "height": 100},
        }


class WindowDiscoveryTests(unittest.TestCase):
    def test_native_enumeration_adds_uwp_frame_and_filters_helpers(self):
        records = [
            {
                "handle": 123,
                "title": "Calculator",
                "class": "ApplicationFrameWindow",
                "visible": True,
                "pid": 10,
                "process_name": "ApplicationFrameHost.exe",
                "left": 0, "top": 0, "right": 400, "bottom": 500,
                "width": 400, "height": 500,
            },
            {
                "handle": 124,
                "title": "Calculator",
                "class": "Windows.UI.Core.CoreWindow",
                "visible": True,
                "pid": 11,
                "process_name": "CalculatorApp.exe",
                "left": 0, "top": 0, "right": 400, "bottom": 500,
                "width": 400, "height": 500,
            },
            {
                "handle": 125,
                "title": "Default IME",
                "class": "IME",
                "visible": False,
                "pid": 11,
                "process_name": "CalculatorApp.exe",
                "left": 0, "top": 0, "right": 0, "bottom": 0,
                "width": 0, "height": 0,
            },
        ]
        with patch("uiautomation.GetRootControl", return_value=_Root()), \
             patch("uiautomation.GetForegroundControl", return_value=None), \
             patch("uiautomation.ControlFromHandle", return_value=None), \
             patch.object(sk, "enumerate_top_level_windows", return_value=records):
            result = sk.list_windows(_Driver(), visible_only=True, include_hidden=False)

        self.assertTrue(result["success"])
        windows = result["data"]["windows"]
        self.assertEqual(len(windows), 1)
        self.assertEqual(windows[0]["window_id"], "0x7B")
        self.assertEqual(windows[0]["app_id"], "calculator")
        self.assertEqual(windows[0]["process_name"], "ApplicationFrameHost.exe")


if __name__ == "__main__":
    unittest.main()
