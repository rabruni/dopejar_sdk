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

Tools registered:
  - log_event          — emit a structured log event
  - emit_metric        — record a counter/gauge/histogram metric
  - get_secret         — retrieve a secret by key
  - validate_schema    — validate JSON data against a Pydantic model name
  - check_rate_limit   — check if a key is within rate limit
  - query_vector       — similarity search in the vector store
  - upsert_vector      — add or update a vector document
  - call_inference     — call the LLM with messages
  - embed_text         — embed text using the configured embedding model
  - check_health       — return health status
  - audit_event        — record an audit log entry
"""
from __future__ import annotations

import asyncio
import json
import os
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

    server = Server("platform-sdk")

    @server.list_tools()
    async def list_tools() -> list[Tool]:
        return [
            Tool(
                name="log_event",
                description="Emit a structured log event via platform_sdk logging.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "level": {"type": "string", "enum": ["debug", "info", "warning", "error"], "default": "info"},
                        "event": {"type": "string", "description": "Short event name (snake_case)"},
                        "data": {"type": "object", "description": "Additional key-value context"},
                    },
                    "required": ["event"],
                },
            ),
            Tool(
                name="emit_metric",
                description="Record a platform metric (counter, gauge, or histogram).",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "kind": {"type": "string", "enum": ["counter", "gauge", "histogram"]},
                        "name": {"type": "string"},
                        "value": {"type": "number", "default": 1},
                        "labels": {"type": "object"},
                    },
                    "required": ["kind", "name"],
                },
            ),
            Tool(
                name="get_secret",
                description="Retrieve a secret value by key using the configured secrets backend.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "key": {"type": "string", "description": "Secret key name"},
                    },
                    "required": ["key"],
                },
            ),
            Tool(
                name="check_rate_limit",
                description="Check if a key is within rate limit. Returns allowed=true/false.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "key": {"type": "string"},
                        "limit": {"type": "integer", "description": "Max requests per window"},
                        "window_seconds": {"type": "integer", "default": 60},
                    },
                    "required": ["key", "limit"],
                },
            ),
            Tool(
                name="query_vector",
                description="Perform a similarity search in the platform vector store.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Search query text"},
                        "collection": {"type": "string", "default": "default"},
                        "top_k": {"type": "integer", "default": 5},
                    },
                    "required": ["query"],
                },
            ),
            Tool(
                name="upsert_vector",
                description="Add or update a document in the platform vector store.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "id": {"type": "string"},
                        "text": {"type": "string"},
                        "collection": {"type": "string", "default": "default"},
                        "metadata": {"type": "object"},
                    },
                    "required": ["id", "text"],
                },
            ),
            Tool(
                name="call_inference",
                description="Call the configured LLM with a list of messages.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "messages": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "role": {"type": "string", "enum": ["system", "user", "assistant"]},
                                    "content": {"type": "string"},
                                },
                                "required": ["role", "content"],
                            },
                        },
                        "model": {"type": "string"},
                        "max_tokens": {"type": "integer", "default": 1024},
                        "temperature": {"type": "number", "default": 0.7},
                    },
                    "required": ["messages"],
                },
            ),
            Tool(
                name="embed_text",
                description="Embed text(s) into vectors using the configured embedding model.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "texts": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "List of strings to embed",
                        },
                        "model": {"type": "string"},
                    },
                    "required": ["texts"],
                },
            ),
            Tool(
                name="check_health",
                description="Return the platform health status (liveness and readiness).",
                inputSchema={
                    "type": "object",
                    "properties": {},
                },
            ),
            Tool(
                name="audit_event",
                description="Record an append-only audit event.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "actor_id": {"type": "string"},
                        "action": {"type": "string"},
                        "resource_type": {"type": "string"},
                        "resource_id": {"type": "string"},
                        "outcome": {"type": "string", "enum": ["success", "failure", "denied"], "default": "success"},
                        "metadata": {"type": "object"},
                    },
                    "required": ["actor_id", "action", "resource_type", "resource_id"],
                },
            ),
        ]

    @server.call_tool()
    async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
        try:
            result = await _dispatch_tool(name, arguments)
            return [TextContent(type="text", text=json.dumps(result, default=str))]
        except Exception as exc:
            return [TextContent(type="text", text=json.dumps({"error": str(exc)}))]

    return server, stdio_server


async def _dispatch_tool(name: str, args: dict[str, Any]) -> Any:
    """Route tool calls to the appropriate platform_sdk function."""
    if name == "log_event":
        from platform_sdk.tier0_core.logging import get_logger
        level = args.get("level", "info")
        event = args["event"]
        data = args.get("data", {})
        log = get_logger()
        getattr(log, level)(event, **data)
        return {"logged": True, "event": event, "level": level}

    elif name == "emit_metric":
        from platform_sdk.tier0_core.metrics import counter, gauge, histogram
        kind = args["kind"]
        metric_name = args["name"]
        value = args.get("value", 1)
        labels = args.get("labels", {})
        if kind == "counter":
            counter(metric_name, **labels).inc(value)
        elif kind == "gauge":
            gauge(metric_name, **labels).set(value)
        elif kind == "histogram":
            histogram(metric_name, **labels).observe(value)
        return {"recorded": True, "kind": kind, "name": metric_name}

    elif name == "get_secret":
        from platform_sdk.tier0_core.secrets import get_secret
        key = args["key"]
        value = get_secret(key)
        # Never return the raw secret — return confirmation only
        return {"key": key, "found": value is not None, "value": "[REDACTED]"}

    elif name == "check_rate_limit":
        from platform_sdk.tier1_runtime.ratelimit import check_rate_limit
        allowed = await check_rate_limit(
            key=args["key"],
            limit=args["limit"],
            window=args.get("window_seconds", 60),
        )
        return {"key": args["key"], "allowed": allowed}

    elif name == "query_vector":
        from platform_sdk.tier3_platform.vector import vector_search
        collection = args.get("collection", "default")
        top_k = args.get("top_k", 5)
        results = await vector_search(
            collection=collection,
            query=args["query"],
            top_k=top_k,
        )
        return {"results": [{"id": r.id, "score": r.score, "metadata": r.metadata} for r in results]}

    elif name == "upsert_vector":
        from platform_sdk.tier3_platform.vector import vector_upsert
        await vector_upsert(
            collection=args.get("collection", "default"),
            id=args["id"],
            text=args["text"],
            metadata=args.get("metadata", {}),
        )
        return {"upserted": True, "id": args["id"]}

    elif name == "call_inference":
        from platform_sdk.tier4_advanced.inference import Message, complete
        messages = [Message(**m) for m in args["messages"]]
        response = await complete(
            messages,
            model=args.get("model"),
            max_tokens=args.get("max_tokens", 1024),
            temperature=args.get("temperature", 0.7),
        )
        return {
            "content": response.content,
            "model": response.model,
            "usage": response.usage,
        }

    elif name == "embed_text":
        from platform_sdk.tier4_advanced.inference import embed
        vectors = await embed(args["texts"], model=args.get("model"))
        return {"embeddings": vectors, "count": len(vectors), "dim": len(vectors[0]) if vectors else 0}

    elif name == "check_health":
        from platform_sdk.tier2_reliability.health import get_health_checker
        checker = get_health_checker()
        status = await checker.check_all()
        return status

    elif name == "audit_event":
        from platform_sdk.tier2_reliability.audit import AuditRecord, audit
        record = AuditRecord(
            actor_id=args["actor_id"],
            action=args["action"],
            resource_type=args["resource_type"],
            resource_id=args["resource_id"],
            outcome=args.get("outcome", "success"),
            metadata=args.get("metadata", {}),
        )
        await audit(record)
        return {"audited": True, "action": args["action"]}

    else:
        raise ValueError(f"Unknown tool: {name!r}")


async def main() -> None:
    server, stdio_server = _build_server()
    async with stdio_server() as streams:
        await server.run(streams[0], streams[1], server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
