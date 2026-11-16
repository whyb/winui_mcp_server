import json
import os
import tempfile
import unittest
from pathlib import Path

from tests.integration.mcp_harness import FreshMcpSession, structured


DEFAULT_APPS = (
    "notepad",
    "calculator",
    "paint",
    "settings",
    "explorer",
    "vscode",
    "edge",
    "chrome",
    "media-player",
)


@unittest.skipUnless(
    os.name == "nt" and os.environ.get("WINUI_RUN_APP_LAUNCH") == "1",
    "Set WINUI_RUN_APP_LAUNCH=1 to launch the common app matrix.",
)
class AppLaunchMatrixTests(unittest.IsolatedAsyncioTestCase):
    async def test_launch_snapshot_and_safe_cleanup(self):
        requested = tuple(
            app.strip()
            for app in os.environ.get("WINUI_LAUNCH_APPS", ",".join(DEFAULT_APPS)).split(",")
            if app.strip()
        )
        with tempfile.TemporaryDirectory(prefix="winui-mcp-matrix-") as root:
            root_path = Path(root)
            note = root_path / "fixture.txt"
            note.write_text("WinUI MCP launch matrix fixture", encoding="utf-8")
            arguments = {
                "notepad": str(note),
                "settings": "display",
                "explorer": str(root_path),
                "vscode": str(root_path),
                "edge": "about:blank",
                "chrome": "about:blank",
            }

            results = {}
            async with FreshMcpSession() as session:
                for app_id in requested:
                    launched = structured(await session.call_tool("launch_app", {
                        "app": app_id,
                        "arguments": arguments.get(app_id),
                        "timeout": 15,
                    }))
                    results[app_id] = launched
                    if not launched["success"]:
                        continue
                    window = launched["data"]["window"]
                    snapshot = structured(await session.call_tool("snapshot", {
                        "window_id": window["window_id"],
                        "depth": 20,
                        "max_nodes": 180,
                        "interactive_only": True,
                    }))
                    results[app_id] = {"launch": launched, "snapshot": snapshot}
                    fixture_owned = (
                        app_id in {"notepad", "explorer", "vscode"}
                        and root_path.name.casefold() in window.get("title", "").casefold()
                    )
                    if launched["data"].get("new_window") or fixture_owned:
                        closed = structured(await session.call_tool("window_action", {
                            "window_id": window["window_id"],
                            "action": "close",
                        }))
                        results[app_id]["close"] = closed
                        self.assertTrue(closed["success"], (app_id, closed))

            print(json.dumps({
                app: {
                    "launch": data.get("launch", data).get("success"),
                    "new_window": data.get("launch", {}).get("data", {}).get("new_window"),
                    "snapshot": data.get("snapshot", {}).get("success"),
                    "close": data.get("close", {}).get("success"),
                }
                for app, data in results.items()
            }, ensure_ascii=False, indent=2))

            launched_apps = {
                app for app, data in results.items()
                if isinstance(data, dict) and data.get("launch", data).get("success")
            }
            self.assertIn("notepad", launched_apps)
            self.assertIn("explorer", launched_apps)
            for app_id, data in results.items():
                if app_id not in launched_apps:
                    if app_id in {"chrome", "media-player"}:
                        continue
                    self.fail(f"{app_id} failed to launch: {data}")
                snapshot = data.get("snapshot")
                if snapshot is not None:
                    self.assertTrue(snapshot["success"], (app_id, snapshot))
                    self.assertGreater(snapshot["data"]["stats"]["tree_nodes"], 0, app_id)


if __name__ == "__main__":
    unittest.main()
