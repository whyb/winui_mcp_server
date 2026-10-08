import unittest

from winui_mcp.driver import AppDriver


class _Control:
    def __init__(self, name, children=None):
        self.Name = name
        self._children = children or []

    def Exists(self, maxSearchSeconds=0):
        return True

    def GetChildren(self):
        return self._children


class ControlRefTests(unittest.TestCase):
    def test_resolve_ref_walks_child_indexes(self):
        leaf = _Control("Save")
        middle = _Control("Panel", [leaf])
        root = _Control("Window", [middle])
        driver = AppDriver.__new__(AppDriver)
        driver._window = root
        driver._timeout = 5
        driver._pid = 0
        driver._hwnd = 0

        resolved = driver.resolve_ref("0.0.0")

        self.assertIs(resolved, leaf)

    def test_dump_tree_uses_window_relative_ref_for_subtree(self):
        leaf = _Control("Save")
        middle = _Control("Panel", [leaf])
        root = _Control("Window", [middle])
        driver = AppDriver.__new__(AppDriver)
        driver._window = root
        driver._timeout = 5
        driver._pid = 0
        driver._hwnd = 0

        tree = driver.dump_tree(middle, max_depth=1, detailed=False, max_nodes=5)

        self.assertEqual(tree["ref"], "0.0")
        self.assertEqual(tree["children"][0]["ref"], "0.0.0")

    def test_resolve_ref_rejects_stale_path(self):
        driver = AppDriver.__new__(AppDriver)
        driver._window = _Control("Window")
        driver._timeout = 5
        driver._pid = 0
        driver._hwnd = 0

        with self.assertRaises(LookupError):
            driver.resolve_ref("0.4")


if __name__ == "__main__":
    unittest.main()
