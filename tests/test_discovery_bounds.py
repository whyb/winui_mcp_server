import unittest

from winui_mcp import skills_library as sk
from winui_mcp.driver import AppDriver


class _Rect:
    left = 0
    top = 0
    right = 10
    bottom = 10

    def width(self):
        return 10

    def height(self):
        return 10


class _Control:
    def __init__(self, name, children=None):
        self.Name = name
        self.ClassName = "Control"
        self.AutomationId = ""
        self.ControlTypeName = "ButtonControl"
        self.IsOffscreen = False
        self.BoundingRectangle = _Rect()
        self._children = children or []
        self.pattern_lookups = 0

    def GetChildren(self):
        return self._children

    def GetValuePattern(self):
        self.pattern_lookups += 1
        raise RuntimeError("unsupported")


class _Driver:
    def __init__(self, matches):
        self.matches = matches

    def find_by_name(self, name, partial=True):
        return self.matches

    def get_search_errors(self):
        return []

    def _get_control_info(self, control, detailed=True):
        return {"class": control.ClassName, "name": control.Name, "detailed": detailed}


class DiscoveryBoundsTests(unittest.TestCase):
    def test_summary_info_skips_pattern_probes(self):
        control = _Control("Button")
        info = AppDriver._get_control_info(control, detailed=False)
        self.assertEqual(info["name"], "Button")
        self.assertNotIn("patterns", info)
        self.assertEqual(control.pattern_lookups, 0)

    def test_dump_tree_respects_max_nodes(self):
        child1 = _Control("One")
        child2 = _Control("Two")
        root = _Control("Root", [child1, child2])
        driver = AppDriver.__new__(AppDriver)

        tree = driver.dump_tree(root, max_depth=3, detailed=False, max_nodes=2)

        self.assertEqual(tree["node_count"], 2)
        self.assertIs(tree["truncated"], True)
        self.assertEqual(tree["omitted_children"], 1)

    def test_find_control_pages_compact_matches(self):
        driver = _Driver([_Control("A"), _Control("B"), _Control("C")])
        result = sk.find_control(driver, name="Item", limit=1, offset=1)

        self.assertTrue(result["success"])
        self.assertEqual(result["data"]["total"], 3)
        self.assertEqual(result["data"]["returned"], 1)
        self.assertEqual(result["data"]["controls"][0]["name"], "B")
        self.assertIs(result["data"]["truncated"], True)


if __name__ == "__main__":
    unittest.main()
