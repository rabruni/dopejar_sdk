"""
platform_sdk._registry
─────────────────────────
Internal module registry — the single source of truth for which modules
exist and which MCP tools each one exposes.

Adding a new module:
  1. Implement it in the right tier using the 5-phase pattern
  2. Add ``__sdk_export__`` to the module (see MODULES.md for the schema)
  3. Add one tuple to TIER_MODULES below

After step 3, the module is automatically available to:
  - ``_registry.collect_mcp_tools()``  → MCP server (no mcp_server.py changes)
  - ``agent.py`` / ``service.py``      → still require a one-line explicit import
"""
from __future__ import annotations

import importlib
from typing import Any

# ---------------------------------------------------------------------------
# Ordered list of (tier_path, module_name) for all *implemented* modules.
# Deferred/stub modules are intentionally omitted to avoid import errors
# when their optional dependencies are not installed.
# ---------------------------------------------------------------------------
TIER_MODULES: list[tuple[str, str]] = [
    # tier0_core — foundational layer
    ("tier0_core", "identity"),
    ("tier0_core", "logging"),
    ("tier0_core", "errors"),
    ("tier0_core", "config"),
    ("tier0_core", "secrets"),
    ("tier0_core", "data"),
    ("tier0_core", "metrics"),
    ("tier0_core", "ledger"),
    # tier1_runtime — request-level safety
    ("tier1_runtime", "context"),
    ("tier1_runtime", "validate"),
    ("tier1_runtime", "serialize"),
    ("tier1_runtime", "retry"),
    ("tier1_runtime", "ratelimit"),
    ("tier1_runtime", "middleware"),
    # tier2_reliability — production operations
    ("tier2_reliability", "health"),
    ("tier2_reliability", "audit"),
    ("tier2_reliability", "cache"),
    # tier3_platform — cross-service patterns
    ("tier3_platform", "authorization"),
    ("tier3_platform", "notifications"),
    ("tier3_platform", "vector"),
    # tier4_advanced — GenAI and advanced capabilities
    ("tier4_advanced", "inference"),
    ("tier4_advanced", "llm_obs"),
]


def collect_mcp_tools() -> list[tuple[dict[str, Any], Any]]:
    """
    Discover all MCP tools registered across tier modules.

    Iterates ``TIER_MODULES``, imports each one, reads its
    ``__sdk_export__["mcp_tools"]`` list, resolves the handler callable,
    and returns a flat list of ``(tool_spec, handler_fn)`` pairs.

    The handler functions live in the modules that own the capability —
    mcp_server.py never needs to import from tier modules directly.

    Returns:
        List of ``(spec_dict, async_callable)`` where spec_dict has keys:
        ``name``, ``description``, ``schema``.
    """
    tools: list[tuple[dict[str, Any], Any]] = []

    for tier_path, module_name in TIER_MODULES:
        qualified = f"platform_sdk.{tier_path}.{module_name}"
        try:
            mod = importlib.import_module(qualified)
        except ImportError:
            # Skip modules whose optional dependencies are not installed.
            continue

        export_meta: dict[str, Any] | None = getattr(mod, "__sdk_export__", None)
        if not export_meta or "mcp_tools" not in export_meta:
            continue

        for tool_spec in export_meta["mcp_tools"]:
            handler_name: str | None = tool_spec.get("handler")
            if not handler_name:
                continue
            handler = getattr(mod, handler_name, None)
            if handler is None:
                continue
            # Strip internal "handler" key — MCP protocol does not need it
            clean_spec = {k: v for k, v in tool_spec.items() if k != "handler"}
            tools.append((clean_spec, handler))

    return tools
