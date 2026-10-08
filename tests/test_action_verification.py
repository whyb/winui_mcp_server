import unittest
from unittest.mock import patch

import driver
import skills_library as sk
from driver import AppDriver


class _TogglePattern:
    def __init__(self, state=0):
        self.ToggleState = state

    def Toggle(self):
        self.ToggleState = 0 if self.ToggleState == 1 else 1


class _ToggleControl:
    def __init__(self, readable=True):
        self.pattern = _TogglePattern()
        self.readable = readable
        self.clicked = False

    def GetTogglePattern(self):
        if not self.readable:
            raise RuntimeError("unsupported")
        return self.pattern

    def Click(self):
        self.clicked = True


class _ValuePattern:
    def __init__(self, value, accept=True):
        self.Value = value
        self.accept = accept

    def SetValue(self, value):
        if self.accept:
            self.Value = value
        return True


class _ValueControl:
    def __init__(self, value, accept=True):
        self.pattern = _ValuePattern(value, accept)

    def GetValuePattern(self):
        return self.pattern


class _Item:
    def __init__(self, name):
        self.Name = name

    def Click(self):
        pass

    def GetChildren(self):
        return []


class _Combo:
    def __init__(self, selected_name):
        self.Name = "Combo"
        self.items = [_Item("Alpha"), _Item("Beta")]
        self.selected_name = selected_name

    def Click(self):
        pass

    def GetExpandCollapsePattern(self):
        class _Expand:
            def Expand(self):
                pass

            def Collapse(self):
                pass

        return _Expand()

    def GetChildren(self):
        return self.items

    def GetSelectionPattern(self):
        return self

    def GetSelection(self):
        return [_Item(self.selected_name)]


class ActionVerificationTests(unittest.TestCase):
    def setUp(self):
        self.driver = AppDriver.__new__(AppDriver)
        self.driver.focus = lambda: None
        self.sleep_patch = patch.object(driver.time, "sleep", return_value=None)
        self.sleep_patch.start()

    def tearDown(self):
        self.sleep_patch.stop()

    def test_toggle_returns_verified_true(self):
        ctrl = _ToggleControl()
        self.assertIs(self.driver.toggle_checkbox_by_control(ctrl, True), True)
        self.assertEqual(ctrl.pattern.ToggleState, 1)

    def test_toggle_returns_none_when_state_is_unreadable(self):
        ctrl = _ToggleControl(readable=False)
        self.assertIsNone(self.driver.toggle_checkbox_by_control(ctrl, True))
        self.assertTrue(ctrl.clicked)

    def test_set_value_reports_mismatch(self):
        ctrl = _ValueControl("old", accept=False)
        self.assertIs(self.driver.set_value_by_control(ctrl, "new"), False)

    def test_set_value_skill_reports_failed_verification(self):
        ctrl = _ValueControl("old", accept=False)
        self.driver.find_by_name = lambda name, partial=True: [ctrl]
        self.driver._get_control_info = lambda control: {"name": "Edit"}
        result = sk.set_value_by_name(self.driver, "Edit", "new")
        self.assertFalse(result["success"])
        self.assertIs(result["verified"], True)

    def test_combo_selection_is_verified(self):
        ctrl = _Combo("Beta")
        self.assertIs(self.driver.select_combobox_item_by_control(ctrl, "Beta"), True)


if __name__ == "__main__":
    unittest.main()
