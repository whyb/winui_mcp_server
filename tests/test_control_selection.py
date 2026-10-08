import unittest

import skills_library as sk


class _Control:
    def __init__(self, name):
        self.name = name
        self.clicked = False


class _Driver:
    def __init__(self, matches):
        self.matches = matches
        self.last_partial = None

    def find_by_name(self, name, partial=False):
        self.last_partial = partial
        return self.matches

    def _get_control_info(self, control):
        return {
            "class": "Button",
            "name": control.name,
            "auto_id": "",
            "control_type": "ButtonControl",
        }

    def click_control(self, control):
        control.clicked = True


class ControlSelectionTests(unittest.TestCase):
    def test_name_index_selects_requested_match(self):
        first = _Control("Save")
        second = _Control("Save")
        driver = _Driver([first, second])

        result = sk.click_by_name(driver, "Save", index=1)

        self.assertTrue(result["success"])
        self.assertFalse(first.clicked)
        self.assertTrue(second.clicked)
        self.assertEqual(result["data"]["match_count"], 2)
        self.assertEqual(result["data"]["match_index"], 1)
        self.assertIs(result["data"]["ambiguous"], True)

    def test_exact_flag_is_forwarded(self):
        driver = _Driver([_Control("Save")])
        result = sk.click_by_name(driver, "Save", partial=False)

        self.assertTrue(result["success"])
        self.assertIs(driver.last_partial, False)

    def test_negative_index_is_rejected(self):
        driver = _Driver([_Control("Save")])
        result = sk.click_by_name(driver, "Save", index=-1)

        self.assertFalse(result["success"])
        self.assertIn("non-negative", result["message"])


if __name__ == "__main__":
    unittest.main()
