import os
import unittest
from unittest.mock import patch

from winui_mcp import apps


class AppCatalogTests(unittest.TestCase):
    def test_aliases_are_case_insensitive(self):
        self.assertEqual(apps.get_profile("CALC").id, "calculator")
        self.assertEqual(apps.get_profile("vs code").id, "vscode")
        self.assertEqual(apps.get_profile("msedge.exe").id, "edge")

    def test_profile_match_prefers_process_name(self):
        profile = apps.match_profile("Untitled - Notepad", "notepad.exe")
        self.assertEqual(profile.id, "notepad")

    def test_public_catalog_does_not_expose_install_paths(self):
        with patch.object(apps, "resolve_launch_plan", side_effect=apps.resolve_launch_plan):
            catalog = apps.list_app_profiles()
        self.assertTrue(catalog)
        serialized = repr(catalog)
        self.assertNotIn("Program Files", serialized)
        self.assertNotIn(os.path.expanduser("~"), serialized)
        self.assertNotIn("launch_targets", serialized)

    def test_executable_resolution_uses_path_before_registry(self):
        with patch.object(apps, "resolve_executable", wraps=apps.resolve_executable), \
             patch.object(apps, "_registry_app_path", return_value=None), \
             patch.object(apps.shutil, "which", return_value=None):
            self.assertIsNone(apps.resolve_executable("definitely-not-installed-42.exe"))

    def test_launch_executable_uses_argument_without_shell(self):
        plan = apps.LaunchPlan(
            app=apps.get_profile("notepad"),
            target="notepad.exe",
            kind="executable",
            source="test",
        )
        with patch.object(apps, "resolve_launch_plan", return_value=plan), \
             patch.object(apps.os, "name", "nt"), \
             patch.object(apps.subprocess, "Popen") as popen:
            apps.launch_application("notepad", arguments="demo.txt")
        popen.assert_called_once_with(
            ["notepad.exe", "demo.txt"], close_fds=True
        )

    def test_uri_launch_uses_startfile(self):
        plan = apps.LaunchPlan(
            app=apps.get_profile("settings"),
            target="ms-settings:",
            kind="uri",
            source="test",
        )
        with patch.object(apps, "resolve_launch_plan", return_value=plan), \
             patch.object(apps.os, "name", "nt"), \
             patch.object(apps.os, "startfile", create=True) as startfile:
            apps.launch_application("settings", arguments="display")
        startfile.assert_called_once_with("ms-settings:display")


if __name__ == "__main__":
    unittest.main()
