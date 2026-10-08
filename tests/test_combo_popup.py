import unittest
from unittest.mock import patch

from winui_mcp.driver import AppDriver


class _Item:
    def __init__(self, name, children=None):
        self.Name = name
        self.ControlTypeName = "ListItemControl"
        self._children = children or []
        self.clicked = False

    def GetChildren(self):
        return self._children

    def Click(self):
        self.clicked = True


class _Combo:
    def __init__(self, children=None):
        self.Name = "Combo"
        self._children = children or []
        self.selected_name = ""
        self.clicked = False

    def Click(self):
        self.clicked = True

    def GetChildren(self):
        return self._children

    def GetExpandCollapsePattern(self):
        class _Pattern:
            def Expand(self):
                pass

            def Collapse(self):
                pass

        return _Pattern()

    def GetSelectionPattern(self):
        return self

    def GetSelection(self):
        return [_Item(self.selected_name)] if self.selected_name else []


class ComboPopupTests(unittest.TestCase):
    def test_selects_deep_descendant(self):
        target = _Item("Target")
        nested = _Item("Nested", [_Item("Deeper", [target])])
        combo = _Combo([nested])
        target.Click = lambda: setattr(combo, "selected_name", "Target")
        driver = AppDriver.__new__(AppDriver)
        with patch("driver.time.sleep", return_value=None):
            state = driver.select_combobox_item_by_control(combo, "Target")
        self.assertIs(state, True)
        self.assertEqual(combo.selected_name, "Target")

    def test_finds_item_in_separate_popup_surface(self):
        combo = _Combo()
        popup_item = _Item("PopupValue")
        driver = AppDriver.__new__(AppDriver)
        driver.find_by_name = lambda name, partial=True: [popup_item]
        popup_item.Click = lambda: setattr(combo, "selected_name", "PopupValue")
        with patch("driver.time.sleep", return_value=None):
            state = driver.select_combobox_item_by_control(combo, "PopupValue")
        self.assertIs(state, True)


if __name__ == "__main__":
    unittest.main()
