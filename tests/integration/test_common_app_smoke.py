import os
import unittest

from tests.integration.mcp_harness import FreshMcpSession, structured


DEFAULT_APPS = ("settings", "explorer", "vscode", "edge")


@unittest.skipUnless(
    os.name == "nt" and os.environ.get("WINUI_RUN_APP_SMOKE") == "1",
    "Set WINUI_RUN_APP_SMOKE=1 to inspect live common app windows.",
)
class CommonAppSmokeTests(unittest.IsolatedAsyncioTestCase):
    async def test_snapshot_existing_common_app_windows(self):
        requested = tuple(
            app.strip()
            for app in os.environ.get("WINUI_SMOKE_APPS", ",".join(DEFAULT_APPS)).split(",")
            if app.strip()
        )
        async with FreshMcpSession() as session:
            listed = structured(await session.call_tool("list_windows", {
                "visible_only": True,
                "include_hidden": False,
            }))
            self.assertTrue(listed["success"], listed)
            windows = listed["data"]["windows"]
            found = {}
            for app_id in requested:
                found[app_id] = next(
                    (window for window in windows if window.get("app_id") == app_id),
                    None,
                )

            inspected = []
            for app_id, window in found.items():
                if window is None:
                    continue
                result = structured(await session.call_tool("snapshot", {
                    "window_id": window["window_id"],
                    "depth": 20,
                    "max_nodes": 180,
                    "interactive_only": True,
                }))
                self.assertTrue(result["success"], (app_id, result))
                self.assertGreater(result["data"]["stats"]["tree_nodes"], 0, app_id)
                inspected.append(app_id)

            if not inspected:
                self.skipTest(f"No requested app windows are currently open: {requested}")


if __name__ == "__main__":
    unittest.main()
