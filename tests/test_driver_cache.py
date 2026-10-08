import unittest
from unittest.mock import Mock, patch

from winui_mcp import driver
from winui_mcp.driver import AppDriver


class _Window:
    def __init__(self, exists=True, handle=10):
        self._exists = exists
        self.NativeWindowHandle = handle

    def Exists(self, maxSearchSeconds=0):
        return self._exists


class DriverCacheTests(unittest.TestCase):
    def tearDown(self):
        driver.clear_driver_cache()

    def test_stale_cached_driver_does_not_create_new_binding(self):
        key = ("App", None, None)
        stale = Mock()
        type(stale).window = property(
            lambda self: (_ for _ in ()).throw(RuntimeError("closed"))
        )
        driver._driver_cache[key] = stale

        with patch.object(driver, "AppDriver") as app_driver:
            with self.assertRaises(RuntimeError) as raised:
                driver.get_cached_driver("App")

        app_driver.assert_not_called()
        self.assertIn("reset_driver", str(raised.exception))

    def test_window_property_does_not_retarget_dead_window(self):
        app = AppDriver.__new__(AppDriver)
        app._window = _Window(exists=False)
        app._pid = 100
        app._hwnd = 10
        app._window_title = "App"
        app._window_class = None
        app._process_name = None
        app._timeout = 5
        app.find_main_window = Mock(side_effect=AssertionError("must not retarget"))

        with self.assertRaises(RuntimeError) as raised:
            _ = app.window

        app.find_main_window.assert_not_called()
        self.assertEqual(app.window_identity(), (100, 10))
        self.assertIn("reset_driver", str(raised.exception))


if __name__ == "__main__":
    unittest.main()
