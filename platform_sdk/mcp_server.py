"""
platform_sdk.mcp_server
─────────────────────────
Exposes platform_sdk capabilities as MCP (Model Context Protocol) tools so
Claude, Cursor, and other MCP-compatible agents can call SDK functionality
directly as tools — without writing raw HTTP requests or importing Python.

Start the server::

    python -m platform_sdk.mcp_server
    # or
    uvx platform-sdk-mcp  (after publishing)

Configure in Claude Desktop (.claude/config.json)::

    {
      "mcpServers": {
        "platform-sdk": {
          "command": "python",
          "args": ["-m", "platform_sdk.mcp_server"],
          "cwd": "/path/to/your/project"
        }
      }
    }

Tools are discovered automatically from ``__sdk_export__["mcp_tools"]`` on
each tier module. To add a new MCP tool:
  1. Add a ``_mcp_<tool_name>`` handler in the owning tier module
  2. Add the tool spec to the module's ``__sdk_export__["mcp_tools"]`` list
  3. Add the module to ``_registry.TIER_MODULES`` if it isn't already there

mcp_server.py never needs to be edited to add new tools.
"""
from __future__ import annotations

import asyncio
import json
from typing import Any


def _build_server() -> Any:
    """Build and return the MCP server instance."""
    try:
        from mcp.server import Server  # type: ignore[import]
        from mcp.server.stdio import stdio_server  # type: ignore[import]
        from mcp.types import TextContent, Tool  # type: ignore[import]
    except ImportError as exc:
        raise ImportError(
            "Install the MCP package to run the MCP server: pip install mcp"
        ) from exc

    from platform_sdk._registry import collect_mcp_tools

    # Discover tools at server startup — no hardcoded list
    _mcp_tools = collect_mcp_tools()
    _tool_index: dict[str, Any] = {spec["name"]: handler for spec, handler in _mcp_tools}

    server = Server("platform-sdk")

    @server.list_tools()
    async def list_tools() -> list[Tool]:
        return [
            Tool(
                name=spec["name"],
                description=spec["description"],
                inputSchema=spec["schema"],
            )
            for spec, _ in _mcp_tools
        ]

    @server.call_tool()
    async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
        try:
            handler = _tool_index.get(name)
            if handler is None:
                raise ValueError(f"Unknown tool: {name!r}")
            result = await handler(arguments)
            return [TextContent(type="text", text=json.dumps(result, default=str))]
        except Exception as exc:
            return [TextContent(type="text", text=json.dumps({"error": str(exc)}))]

    return server, stdio_server


async def main() -> None:
    server, stdio_server = _build_server()
    async with stdio_server() as streams:
        await server.run(streams[0], streams[1], server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
