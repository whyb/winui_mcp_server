import unittest

from winui_mcp.driver import AppDriver, ElementReference, format_window_id, parse_window_id


class _Control:
    def __init__(self, name="OK", runtime_id=(1, 2), handle=0, exists=True):
        self.Name = name
        self.ClassName = "ButtonControl"
        self.AutomationId = "okButton"
        self.ControlTypeName = "ButtonControl"
        self.NativeWindowHandle = handle
        self._runtime_id = runtime_id
        self._exists = exists

    def Exists(self, maxSearchSeconds=0):
        return self._exists

    def GetRuntimeId(self):
        return self._runtime_id


def _driver():
    driver = AppDriver.__new__(AppDriver)
    driver._window = None
    driver._pid = 100
    driver._hwnd = 10
    driver._timeout = 0.01
    driver._element_refs = {}
    driver._element_identity_ids = {}
    driver._element_sequence = 0
    driver._snapshot_generation = 0
    return driver


class ElementReferenceTests(unittest.TestCase):
    def test_register_assigns_semantic_ids_and_deduplicates(self):
        driver = _driver()
        control = _Control()
        first = driver.register_element(control, "0.1")
        second = driver.register_element(control, "0.2")
        self.assertEqual(first, "e1")
        self.assertEqual(second, "e1")
        self.assertEqual(len(driver._element_refs), 1)

    def test_resolve_uses_live_control(self):
        driver = _driver()
        control = _Control()
        element_id = driver.register_element(control, "0.1")
        self.assertIs(driver.resolve_element(element_id), control)

    def test_reset_invalidates_previous_element_ids(self):
        driver = _driver()
        element_id = driver.register_element(_Control(), "0.1")
        generation = driver.reset_element_refs()
        self.assertEqual(generation, 1)
        with self.assertRaises(LookupError):
            driver.resolve_element(element_id)

    def test_semantic_match_accepts_recreated_runtime_identity(self):
        driver = _driver()
        stored = ElementReference(
            element_id="e1",
            control=_Control(exists=False),
            tree_ref="0.1",
            identity=("runtime", (1, 2)),
            class_name="ButtonControl",
            name="OK",
            auto_id="okButton",
        )
        replacement = _Control(runtime_id=(9, 9))
        self.assertTrue(driver._semantic_element_match(replacement, stored))

    def test_window_id_round_trip(self):
        self.assertEqual(parse_window_id("0x1A"), 26)
        self.assertEqual(parse_window_id("26"), 26)
        self.assertEqual(format_window_id(26), "0x1A")


if __name__ == "__main__":
    unittest.main()
