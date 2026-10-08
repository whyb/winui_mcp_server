import unittest

from winui_mcp import skills_library as sk
from winui_mcp.driver import AppDriver


class _Control:
    def __init__(self, name, children=None, fail_children=False):
        self.Name = name
        self.ClassName = "Control"
        self._children = children or []
        self.fail_children = fail_children

    def GetChildren(self):
        if self.fail_children:
            raise RuntimeError("access denied")
        return self._children


class SearchErrorTests(unittest.TestCase):
    def test_bad_branch_does_not_hide_healthy_sibling(self):
        good = _Control("Target")
        bad = _Control("Broken", fail_children=True)
        root = _Control("Root", [bad, good])
        driver = AppDriver.__new__(AppDriver)
        driver._search_errors = []

        matches = driver.find_by_name("Target", control=root, partial=False)

        self.assertEqual(matches, [good])
        self.assertEqual(len(driver.get_search_errors()), 1)

    def test_find_control_reports_search_errors(self):
        class _Driver:
            def find_by_name(self, name, partial=True):
                return []

            def get_search_errors(self):
                return [{"name": "Broken", "error": "access denied"}]

        result = sk.find_control(_Driver(), name="Target")

        self.assertFalse(result["success"])
        self.assertIn("inaccessible branches", result["message"])
        self.assertEqual(len(result["data"]["search_errors"]), 1)


if __name__ == "__main__":
    unittest.main()
