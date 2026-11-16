# MCP Client Configuration

The server uses the standard MCP **stdio** transport:

```text
command: uvx
args:    ["winui-mcp-server"]
```

Use `uvx` for installed users. To run directly from a checkout, use:

```text
uv run --directory <checkout> winui-mcp
```

Client configuration formats change over time. The snippets below cover current
common formats; consult the client documentation if its schema has changed.

## Codex

Project or global `config.toml`:

```toml
[mcp_servers.winui]
command = "uvx"
args = ["winui-mcp-server"]
```

## Claude Code

Project `.mcp.json` or the equivalent global MCP configuration:

```json
{
  "mcpServers": {
    "winui": {
      "command": "uvx",
      "args": ["winui-mcp-server"]
    }
  }
}
```

## OpenCode V2

`opencode.jsonc`:

```jsonc
{
  "$schema": "https://opencode.ai/config.json",
  "mcp": {
    "servers": {
      "winui": {
        "type": "local",
        "command": ["uvx", "winui-mcp-server"]
      }
    }
  }
}
```

## VS Code / GitHub Copilot

`.vscode/mcp.json`:

```json
{
  "servers": {
    "winui": {
      "type": "stdio",
      "command": "uvx",
      "args": ["winui-mcp-server"]
    }
  }
}
```

## Cline

Add an MCP server with this stdio command and arguments, or use the equivalent
`mcpServers` JSON entry supported by the installed Cline version:

```json
{
  "mcpServers": {
    "winui": {
      "command": "uvx",
      "args": ["winui-mcp-server"]
    }
  }
}
```

## Kimi Code, DeepSeek Harness, Trae, and other clients

Use the generic stdio command above through the client's MCP settings UI or JSON
configuration. The server relies on standard MCP tools, structured tool results,
server instructions, and optional resources and prompts. If a client ignores
resources or prompts, the tool workflow in `docs/AGENT_GUIDE.md` remains fully
functional.

## Local development

Conda users can avoid rebuilding a wheel:

```json
{
  "mcpServers": {
    "winui": {
      "command": "conda",
      "args": [
        "run",
        "-n",
        "winui_mcp_server",
        "python",
        "-m",
        "winui_mcp.mcp_server"
      ]
    }
  }
}
```

This local command is not the recommended configuration for end users.
