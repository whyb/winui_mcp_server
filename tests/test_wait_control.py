import unittest
from unittest.mock import patch

from winui_mcp import skills_library as sk


class _Control:
    def __init__(self, name, actionable):
        self.name = name
        self.actionable = actionable


class _Driver:
    def __init__(self, samples):
        self.samples = list(samples)

    def find_by_name(self, name, partial=True):
        if len(self.samples) > 1:
            return self.samples.pop(0)
        return self.samples[0]

    def is_control_actionable(self, control):
        return control.actionable

    def control_signature(self, control):
        return (control.name,)

    def _get_control_info(self, control):
        return {"name": control.name, "class": "Button"}


class WaitControlTests(unittest.TestCase):
    def test_hidden_control_is_not_treated_as_appeared(self):
        hidden = _Control("Loading", False)
        visible = _Control("Loading", True)
        driver = _Driver([[hidden], [visible], [visible]])

        with patch("time.sleep", return_value=None):
            result = sk.wait_for_control(driver, name="Loading", timeout=2, poll_interval=0)

        self.assertTrue(result["success"])
        self.assertIs(result["verified"], True)
        self.assertEqual(result["data"]["control"]["name"], "Loading")

    def test_disappear_ignores_non_actionable_matches(self):
        hidden = _Control("Loading", False)
        driver = _Driver([[hidden]])

        result = sk.wait_for_control(driver, name="Loading", timeout=1, disappear=True)

        self.assertTrue(result["success"])
        self.assertIs(result["verified"], True)

    def test_timeout_reports_unverified(self):
        hidden = _Control("Loading", False)
        driver = _Driver([[hidden]])

        result = sk.wait_for_control(driver, name="Loading", timeout=-1)

        self.assertFalse(result["success"])
        self.assertIs(result["verified"], False)


if __name__ == "__main__":
    unittest.main()
