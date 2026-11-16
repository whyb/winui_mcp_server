import os
import tempfile
import unittest
from pathlib import Path

from tests.integration.mcp_harness import FreshMcpSession, structured


@unittest.skipUnless(
    os.name == "nt" and os.environ.get("WINUI_RUN_INTEGRATION") == "1",
    "Set WINUI_RUN_INTEGRATION=1 to run live MCP integration tests.",
)
class McpStdioIntegrationTests(unittest.IsolatedAsyncioTestCase):
    async def test_fresh_server_exposes_structured_tools(self):
        async with FreshMcpSession() as session:
            tools = await session.list_tools()
            names = {tool.name for tool in tools.tools}
            self.assertIn("launch_app", names)
            self.assertIn("snapshot", names)
            self.assertIn("run_actions", names)

            result = structured(await session.call_tool("list_apps", {}))
            self.assertTrue(result["success"])
            self.assertIn("notepad", {app["id"] for app in result["data"]["apps"]})

    async def test_notepad_launch_snapshot_and_close(self):
        temp_path = None
        async with FreshMcpSession() as session:
            try:
                with tempfile.NamedTemporaryFile(
                    mode="w", suffix=".txt", prefix="winui-mcp-smoke-",
                    delete=False, encoding="utf-8"
                ) as handle:
                    handle.write("winui mcp integration fixture")
                    temp_path = handle.name

                launched = structured(await session.call_tool("launch_app", {
                    "app": "notepad",
                    "arguments": temp_path,
                    "timeout": 15,
                }))
                self.assertTrue(launched["success"], launched)
                window_id = launched["data"]["window"]["window_id"]
                self.assertTrue(window_id.startswith("0x"))

                snapshot = structured(await session.call_tool("snapshot", {
                    "window_id": window_id,
                    "depth": 12,
                    "max_nodes": 250,
                    "interactive_only": True,
                }))
                self.assertTrue(snapshot["success"], snapshot)
                self.assertGreater(snapshot["data"]["stats"]["tree_nodes"], 0)

                elements = snapshot["data"]["elements"]
                if elements:
                    hovered = structured(await session.call_tool("hover", {
                        "window_id": window_id,
                        "element_id": elements[0]["element_id"],
                    }))
                    self.assertTrue(hovered["success"], hovered)

                batched = structured(await session.call_tool("run_actions", {
                    "window_id": window_id,
                    "steps": [{"action": "focus_window"}],
                    "snapshot_after": False,
                }))
                self.assertTrue(batched["success"], batched)

                closed = structured(await session.call_tool("window_action", {
                    "window_id": window_id,
                    "action": "close",
                }))
                self.assertTrue(closed["success"], closed)
            finally:
                if temp_path:
                    Path(temp_path).unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
