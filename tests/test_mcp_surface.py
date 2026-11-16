import asyncio
import unittest

from winui_mcp.mcp_server import _json, mcp


class McpSurfaceTests(unittest.TestCase):
    def test_documented_tool_count_and_agent_first_names(self):
        tools = asyncio.run(mcp.list_tools())
        names = {tool.name for tool in tools}
        self.assertEqual(len(tools), 31)
        self.assertTrue({
            "launch_app", "snapshot", "run_actions", "ocr_scan", "reset_driver"
        }.issubset(names))

    def test_tools_have_structured_output_and_annotations(self):
        tools = {tool.name: tool for tool in asyncio.run(mcp.list_tools())}
        self.assertIsNotNone(tools["snapshot"].outputSchema)
        self.assertTrue(tools["snapshot"].annotations.readOnlyHint)
        self.assertTrue(tools["run_actions"].annotations.destructiveHint)
        self.assertFalse(tools["click"].annotations.readOnlyHint)

    def test_action_schema_is_typed(self):
        tool = {item.name: item for item in asyncio.run(mcp.list_tools())}["run_actions"]
        definitions = tool.inputSchema.get("$defs", {})
        step_schema = next(
            schema for name, schema in definitions.items() if name.endswith("ActionStep")
        )
        action_enum = step_schema["properties"]["action"]["enum"]
        self.assertIn("click", action_enum)
        self.assertIn("type_text", action_enum)
        self.assertIn("element_id", step_schema["properties"])

    def test_tool_returns_structured_content(self):
        _, structured = asyncio.run(mcp.call_tool("list_apps", {}))
        self.assertTrue(structured["success"])
        self.assertIn("notepad", {app["id"] for app in structured["data"]["apps"]})
        self.assertNotIn("Program Files", repr(structured))

    def test_descriptor_number_matches_documented_families(self):
        tools = asyncio.run(mcp.list_tools())
        descriptions = "\n".join(tool.description or "" for tool in tools)
        self.assertIn("Prefer snapshot", descriptions)
        self.assertIn("legacy ref", descriptions)

    def test_json_output_is_compact(self):
        payload = _json({"success": True, "data": {"value": 1}})
        self.assertNotIn("\n", payload)
        self.assertEqual(payload, '{"success":true,"data":{"value":1}}')


if __name__ == "__main__":
    unittest.main()
