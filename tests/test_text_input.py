import unittest
from unittest.mock import Mock, patch

import driver
from driver import AppDriver


class TextInputTests(unittest.TestCase):
    def test_literal_braces_are_escaped(self):
        self.assertEqual(driver._escape_sendkeys_text("{x}"), "{{}x{}}")

    def test_type_text_sends_escaped_literal_text(self):
        app = AppDriver.__new__(AppDriver)
        app._ensure_process_foreground = lambda: None
        with patch.object(driver.auto, "SendKeys") as send_keys, \
             patch.object(driver.time, "sleep", return_value=None):
            app.type_text("{value}")
        send_keys.assert_called_once_with("{{}value{}}")

    def test_long_press_supports_special_key_and_always_releases(self):
        app = AppDriver.__new__(AppDriver)
        app._ensure_process_foreground = lambda: None
        keybd_event = Mock()
        with patch.object(driver.ctypes.windll.user32, "keybd_event", keybd_event), \
             patch.object(driver.time, "sleep", return_value=None):
            app.long_press_key("{Enter}", duration=0.2)
        self.assertEqual(keybd_event.call_count, 2)
        self.assertEqual(keybd_event.call_args_list[0].args[2], 0)
        self.assertEqual(keybd_event.call_args_list[1].args[2], 2)


if __name__ == "__main__":
    unittest.main()
