import unittest

from winui_mcp import skills_library as sk


class _Rect:
    left = 10
    top = 20
    right = 810
    bottom = 620

    def width(self):
        return 800

    def height(self):
        return 600


class _Window:
    Name = "Demo App"
    ClassName = "DemoWindow"
    BoundingRectangle = _Rect()

    def IsMinimize(self):
        return False


class _Control:
    def __init__(self, name, control_type="ButtonControl", value=None):
        self.Name = name
        self.ClassName = "DemoControl"
        self.AutomationId = name.lower().replace(" ", "")
        self.ControlTypeName = control_type
        self.Value = value

    def GetValuePattern(self):
        if self.Value is None:
            raise RuntimeError("no value")
        return self


class _Driver:
    def __init__(self):
        self._window = _Window()
        self._snapshot_generation = 0
        self._controls = {
            "e2": _Control("Save"),
            "e3": _Control("Status", "TextControl", "Ready"),
            "e4": _Control("Editor", "EditControl", "hello"),
        }
        self.clicked = []
        self.typed = []

    @property
    def window(self):
        return self._window

    @property
    def process_name(self):
        return "demo.exe"

    @property
    def window_id(self):
        return "0x10"

    def reset_element_refs(self):
        self._snapshot_generation += 1
        return self._snapshot_generation

    def dump_tree(self, control=None, max_depth=5, detailed=True, max_nodes=300,
                  element_ids=True):
        return {
            "element_id": "e1",
            "ref": "0",
            "name": "Demo App",
            "control_type": "WindowControl",
            "class": "DemoWindow",
            "interactive": False,
            "depth": 0,
            "node_count": 4,
            "truncated": False,
            "children": [
                {
                    "element_id": "e2", "ref": "0.0", "name": "Save",
                    "control_type": "ButtonControl", "class": "Button",
                    "auto_id": "save", "interactive": True, "enabled": True,
                    "visible": True, "offscreen": False, "patterns": ["Invoke"],
                    "depth": 1, "children": [],
                },
                {
                    "element_id": "e3", "ref": "0.1", "name": "Status",
                    "value": "Ready", "control_type": "TextControl",
                    "class": "Text", "auto_id": "status", "interactive": False,
                    "enabled": True, "visible": True, "offscreen": False,
                    "patterns": [], "depth": 1, "children": [],
                },
                {
                    "element_id": "e4", "ref": "0.2", "name": "Editor",
                    "value": "hello", "control_type": "EditControl",
                    "class": "Edit", "auto_id": "editor", "interactive": True,
                    "enabled": True, "visible": True, "offscreen": False,
                    "patterns": ["Value"], "depth": 1, "children": [],
                },
            ],
        }

    def _get_control_info(self, control, detailed=True):
        return {
            "name": control.Name,
            "class": control.ClassName,
            "auto_id": control.AutomationId,
            "control_type": control.ControlTypeName,
            "value": control.Value,
            "patterns": ["Value"] if control.Value is not None else [],
        }

    def resolve_element(self, element_id):
        try:
            return self._controls[element_id]
        except KeyError as exc:
            raise LookupError("stale") from exc

    def click_control(self, control):
        self.clicked.append(control.Name)

    def type_text(self, text, control=None):
        self.typed.append((control.Name if control else None, text))

    def find_by_name(self, name, partial=False):
        return []


class AgentSnapshotTests(unittest.TestCase):
    def test_snapshot_filters_to_interactive_elements(self):
        result = sk.snapshot(_Driver(), depth=5, max_nodes=20, interactive_only=True)
        self.assertTrue(result["success"])
        ids = {item["element_id"] for item in result["data"]["elements"]}
        self.assertEqual(ids, {"e2", "e4"})
        self.assertEqual(result["data"]["window"]["window_id"], "0x10")

    def test_snapshot_query_can_include_noninteractive_text(self):
        result = sk.snapshot(
            _Driver(), interactive_only=False, query="status"
        )
        self.assertTrue(result["success"])
        self.assertEqual(result["data"]["elements"][0]["element_id"], "e3")
        self.assertEqual(result["data"]["elements"][0]["text"], "Ready")

    def test_action_sequence_uses_element_ids(self):
        driver = _Driver()
        result = sk.run_actions(
            driver,
            [
                {"action": "click", "element_id": "e2"},
                {"action": "type_text", "element_id": "e4", "text": "world"},
            ],
            snapshot_after=False,
        )
        self.assertTrue(result["success"])
        self.assertEqual(result["data"]["completed"], 2)
        self.assertEqual(driver.clicked, ["Save"])
        self.assertEqual(driver.typed, [("Editor", "world")])

    def test_action_sequence_stops_on_error(self):
        driver = _Driver()
        result = sk.run_actions(
            driver,
            [
                {"action": "click", "element_id": "missing"},
                {"action": "click", "element_id": "e2"},
            ],
            snapshot_after=False,
        )
        self.assertFalse(result["success"])
        self.assertTrue(result["data"]["stopped_early"])
        self.assertEqual(driver.clicked, [])


if __name__ == "__main__":
    unittest.main()
