import ctypes.wintypes
import os
import unittest

from winui_mcp import driver


class Win32PrototypeTests(unittest.TestCase):
    def test_handle_api_prototypes_are_declared(self):
        self.assertIs(driver._kernel32.OpenProcess.restype, ctypes.wintypes.HANDLE)
        self.assertIsNotNone(driver._psapi.GetModuleBaseNameW.argtypes)
        self.assertIsNotNone(driver._user32.GetWindowThreadProcessId.argtypes)
        self.assertIsNotNone(driver._user32.keybd_event.argtypes)

    def test_process_name_lookup_handles_current_process(self):
        self.assertEqual(driver._get_process_name(os.getpid()).lower(), "python.exe")


if __name__ == "__main__":
    unittest.main()
