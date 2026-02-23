"""
platform_sdk.agent
────────────────────
Agent surface — the minimal, intentionally narrow import contract for AI agents.

Agents (Claude, autonomous tools, MCP clients) should import ONLY from here.
Every symbol in this module is stable, semver-protected, and safe for an agent
to call without understanding service infrastructure.

What is deliberately NOT here
------------------------------
- ``get_session``, ``get_engine``   — agents don't own data; the service layer does
- ``verify_token``, ``get_principal`` — agents don't authenticate users
- ``get_config``, ``get_secret``    — handled by the service the agent runs inside
- ``counter``, ``gauge``, ``histogram`` — infrastructure, not agent concerns
- ``PlatformASGIMiddleware``        — framework middleware, not agent concerns

Usage::

    from platform_sdk.agent import complete, vector_search, observe, get_logger
    # identical symbols available via the top-level package (backward compat):
    from platform_sdk import complete, vector_search

Boundary enforcement::

    from platform_sdk.agent import get_session  # ImportError — boundary enforced
"""
from __future__ import annotations

# ── Inference ─────────────────────────────────────────────────────────────────
from platform_sdk.tier4_advanced.inference import complete, embed, Message

# ── LLM Observability ─────────────────────────────────────────────────────────
from platform_sdk.tier4_advanced.llm_obs import observe, get_llm_tracer, record_inference

# ── Vector / knowledge retrieval ──────────────────────────────────────────────
from platform_sdk.tier3_platform.vector import vector_search, vector_upsert, vector_delete

# ── Logging ───────────────────────────────────────────────────────────────────
from platform_sdk.tier0_core.logging import get_logger

# ── Errors (subset — only what agents need to catch) ─────────────────────────
from platform_sdk.tier0_core.errors import PlatformError, RateLimitError, UpstreamError

__all__ = [
    # inference
    "complete",
    "embed",
    "Message",
    # llm_obs
    "observe",
    "get_llm_tracer",
    "record_inference",
    # vector
    "vector_search",
    "vector_upsert",
    "vector_delete",
    # logging
    "get_logger",
    # errors (agent subset)
    "PlatformError",
    "RateLimitError",
    "UpstreamError",
]

# Frozenset used by tooling to enforce the boundary at import-check time.
_AGENT_SURFACE: frozenset[str] = frozenset(__all__)
