import asyncio
import json
import os
import tempfile
import unittest
import uuid
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
)


@unittest.skipUnless(
    os.name == "nt" and os.environ.get("WINUI_RUN_APP_LAUNCH") == "1",
    "Set WINUI_RUN_APP_LAUNCH=1 to launch the common app matrix.",
)
class AppLaunchMatrixTests(unittest.IsolatedAsyncioTestCase):
    async def _list_window_ids(self, session) -> set[str]:
        listed = structured(await session.call_tool("list_windows", {
            "visible_only": True,
            "include_hidden": False,
        }))
        self.assertTrue(listed["success"], listed)
        return {
            item["window_id"]
            for item in listed["data"]["windows"]
            if item.get("window_id")
        }

    async def _wait_for_window_gone(self, session, window_id: str,
                                    timeout: float = 6.0) -> bool:
        deadline = asyncio.get_running_loop().time() + timeout
        while asyncio.get_running_loop().time() < deadline:
            if window_id not in await self._list_window_ids(session):
                return True
            await asyncio.sleep(0.25)
        return window_id not in await self._list_window_ids(session)

    async def test_launch_snapshot_and_safe_cleanup(self):
        requested = tuple(
            app.strip()
            for app in os.environ.get("WINUI_LAUNCH_APPS", ",".join(DEFAULT_APPS)).split(",")
            if app.strip()
        )
        token = uuid.uuid4().hex[:12]
        with tempfile.TemporaryDirectory(
    prefix="winui-mcp-matrix-", ignore_cleanup_errors=True
) as root:
            root_path = Path(root)
            note = root_path / "fixture.txt"
            note.write_text("WinUI MCP launch matrix fixture", encoding="utf-8")
            edge_page = root_path / f"edge-{token}.html"
            edge_page.write_text(
                f"<!doctype html><title>winui-edge-{token}</title>edge fixture",
                encoding="utf-8",
            )
            chrome_page = root_path / f"chrome-{token}.html"
            chrome_page.write_text(
                f"<!doctype html><title>winui-chrome-{token}</title>chrome fixture",
                encoding="utf-8",
            )
            arguments = {
                "notepad": str(note),
                "settings": "display",
                "explorer": str(root_path),
                "vscode": [
                    f"--user-data-dir={root_path / 'vscode-profile'}",
                    "--new-window",
                    "--disable-extensions",
                    str(root_path),
                ],
                "edge": [
                    f"--user-data-dir={root_path / 'edge-profile'}",
                    "--no-first-run",
                    "--disable-background-mode",
                    "--disable-extensions",
                    f"--app={edge_page.as_uri()}",
                ],
                "chrome": [
                    f"--user-data-dir={root_path / 'chrome-profile'}",
                    "--no-first-run",
                    "--disable-background-mode",
                    "--disable-extensions",
                    f"--app={chrome_page.as_uri()}",
                ],
            }

            results = {}
            async with FreshMcpSession() as session:
                for app_id in requested:
                    launched = structured(await session.call_tool("launch_app", {
                        "app": app_id,
                        "arguments": arguments.get(app_id),
                        "timeout": 20,
                    }))
                    results[app_id] = {"launch": launched}
                    if not launched["success"]:
                        continue
                    window = launched["data"]["window"]
                    window_id = window["window_id"]
                    snapshot = structured(await session.call_tool("snapshot", {
                        "window_id": window_id,
                        "depth": 20,
                        "max_nodes": 180,
                        "interactive_only": True,
                    }))
                    results[app_id]["snapshot"] = snapshot
                    title = str(window.get("title") or "")
                    fixture_owned = (
                        launched["data"].get("new_window")
                        or root_path.name.casefold() in title.casefold()
                        or token in title.casefold()
                    )
                    if fixture_owned:
                        closed = structured(await session.call_tool("window_action", {
                            "window_id": window_id,
                            "action": "close",
                        }))
                        results[app_id]["close"] = closed
                        self.assertTrue(closed["success"], (app_id, closed))
                        self.assertTrue(closed.get("verified"), (app_id, closed))
                        self.assertIn("strategy", closed["data"], (app_id, closed))
                        self.assertTrue(
                            await self._wait_for_window_gone(session, window_id),
                            f"{app_id} window {window_id} is still listed after close: {closed}",
                        )

            print(json.dumps({
                app: {
                    "launch": data["launch"].get("success"),
                    "new_window": data["launch"].get("data", {}).get("new_window"),
                    "snapshot": data.get("snapshot", {}).get("success"),
                    "close": data.get("close", {}).get("success"),
                    "close_strategy": data.get("close", {}).get("data", {}).get("strategy"),
                }
                for app, data in results.items()
            }, ensure_ascii=False, indent=2))

            launched_apps = {
                app for app, data in results.items()
                if data["launch"].get("success")
            }
            if "notepad" in requested:
                self.assertIn("notepad", launched_apps)
            if "explorer" in requested:
                self.assertIn("explorer", launched_apps)
            for app_id, data in results.items():
                if app_id not in launched_apps:
                    if app_id in {"chrome"}:
                        continue
                    self.fail(f"{app_id} failed to launch: {data}")
                snapshot = data.get("snapshot")
                if snapshot is not None:
                    self.assertTrue(snapshot["success"], (app_id, snapshot))
                    self.assertGreater(snapshot["data"]["stats"]["tree_nodes"], 0, app_id)


if __name__ == "__main__":
    unittest.main()
