import asyncio
import unittest

from winui_mcp.mcp_server import _json, mcp


class McpSurfaceTests(unittest.TestCase):
    def test_documented_tool_count_matches_server(self):
        tools = asyncio.run(mcp.list_tools())
        names = {tool.name for tool in tools}
        self.assertEqual(len(tools), 26)
        self.assertIn("reset_driver", names)
        self.assertIn("ocr_scan", names)

    def test_json_output_is_compact(self):
        payload = _json({"success": True, "data": {"value": 1}})
        self.assertNotIn("\n", payload)
        self.assertEqual(payload, '{"success":true,"data":{"value":1}}')


if __name__ == "__main__":
    unittest.main()
