import os
import tempfile
import unittest
from unittest.mock import patch

import config


class ConfigDiscoveryTests(unittest.TestCase):
    def test_environment_path_takes_priority(self):
        with tempfile.TemporaryDirectory() as tmp:
            exe = os.path.join(tmp, "AccessibilityInsights.exe")
            with open(exe, "w", encoding="utf-8") as handle:
                handle.write("")
            with patch.dict(os.environ, {"ACCESSIBILITY_INSIGHTS_PATH": exe}):
                self.assertEqual(config.find_accessibility_insights(), os.path.abspath(exe))

    def test_missing_environment_path_returns_none_when_no_install_found(self):
        with patch.dict(os.environ, {"ACCESSIBILITY_INSIGHTS_PATH": r"C:\missing\AccessibilityInsights.exe"}), \
             patch.object(config, "_candidate_paths", return_value=[]):
            self.assertIsNone(config.find_accessibility_insights())


if __name__ == "__main__":
    unittest.main()
