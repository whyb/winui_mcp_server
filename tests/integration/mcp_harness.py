"""Helpers for launching a fresh MCP server over stdio."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def structured(result) -> dict:
    """Extract structured MCP output across SDK minor versions."""
    structured_content = getattr(result, "structuredContent", None)
    if structured_content is not None:
        return structured_content
    for block in getattr(result, "content", []):
        text = getattr(block, "text", None)
        if text:
            return json.loads(text)
    raise AssertionError("MCP tool did not return structured JSON content")


class FreshMcpSession:
    """Context manager that starts and initializes a fresh stdio MCP server."""

    async def __aenter__(self):
        env = os.environ.copy()
        env.setdefault("PYTHONIOENCODING", "utf-8")
        params = StdioServerParameters(
            command=sys.executable,
            args=["-m", "winui_mcp.mcp_server"],
            cwd=str(PROJECT_ROOT),
            env=env,
        )
        self._stdio = stdio_client(params)
        self.read_stream, self.write_stream = await self._stdio.__aenter__()
        self.session = ClientSession(self.read_stream, self.write_stream)
        await self.session.__aenter__()
        await self.session.initialize()
        return self.session

    async def __aexit__(self, exc_type, exc, traceback):
        try:
            await self.session.__aexit__(exc_type, exc, traceback)
        finally:
            await self._stdio.__aexit__(exc_type, exc, traceback)
