"""
platform_sdk.tier3_platform.agent
───────────────────────────────────
Agent identity and resource quotas. Every AI agent gets a stable identity
(agent_id, agent_type, owner_id) and is subject to platform-enforced resource
limits (token budgets, call rate limits, cost caps).

Prevents runaway agents from exhausting shared resources.

Minimal stack: DEFERRED — add when multiple agents share platform resources.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any


@dataclass
class AgentIdentity:
    agent_id: str
    agent_type: str  # e.g. "qa-agent", "code-review-agent", "data-analyst"
    owner_id: str    # principal_id of the human or service that owns this agent
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentQuota:
    """Resource limits enforced per agent."""
    max_tokens_per_minute: int = 100_000
    max_calls_per_minute: int = 60
    max_cost_per_day_usd: float = 10.0
    max_context_tokens: int = 200_000


@dataclass
class AgentUsage:
    agent_id: str
    tokens_used: int = 0
    calls_made: int = 0
    cost_usd: float = 0.0


class AgentRegistry:
    """In-memory agent registry. Replace with Redis or DB backend in production."""

    def __init__(self) -> None:
        self._agents: dict[str, AgentIdentity] = {}
        self._quotas: dict[str, AgentQuota] = {}
        self._usage: dict[str, AgentUsage] = {}

    def register(
        self,
        agent_id: str,
        agent_type: str,
        owner_id: str,
        quota: AgentQuota | None = None,
        **metadata: Any,
    ) -> AgentIdentity:
        identity = AgentIdentity(
            agent_id=agent_id,
            agent_type=agent_type,
            owner_id=owner_id,
            metadata=metadata,
        )
        self._agents[agent_id] = identity
        self._quotas[agent_id] = quota or AgentQuota()
        self._usage[agent_id] = AgentUsage(agent_id=agent_id)
        return identity

    def get(self, agent_id: str) -> AgentIdentity | None:
        return self._agents.get(agent_id)

    def get_quota(self, agent_id: str) -> AgentQuota:
        return self._quotas.get(agent_id, AgentQuota())

    def get_usage(self, agent_id: str) -> AgentUsage:
        return self._usage.get(agent_id, AgentUsage(agent_id=agent_id))

    def record_usage(
        self, agent_id: str, tokens: int = 0, calls: int = 1, cost_usd: float = 0.0
    ) -> None:
        if agent_id not in self._usage:
            self._usage[agent_id] = AgentUsage(agent_id=agent_id)
        usage = self._usage[agent_id]
        usage.tokens_used += tokens
        usage.calls_made += calls
        usage.cost_usd += cost_usd

    def check_quota(self, agent_id: str) -> bool:
        """Return True if the agent is within quota limits."""
        quota = self.get_quota(agent_id)
        usage = self.get_usage(agent_id)
        return (
            usage.tokens_used < quota.max_tokens_per_minute
            and usage.calls_made < quota.max_calls_per_minute
            and usage.cost_usd < quota.max_cost_per_day_usd
        )


_registry: AgentRegistry | None = None


def get_registry() -> AgentRegistry:
    global _registry
    if _registry is None:
        _registry = AgentRegistry()
    return _registry


def register_agent(
    agent_id: str,
    agent_type: str,
    owner_id: str,
    quota: AgentQuota | None = None,
    **metadata: Any,
) -> AgentIdentity:
    return get_registry().register(agent_id, agent_type, owner_id, quota, **metadata)


def get_agent(agent_id: str) -> AgentIdentity | None:
    return get_registry().get(agent_id)


__all__ = [
    "AgentIdentity", "AgentQuota", "AgentUsage", "AgentRegistry",
    "get_registry", "register_agent", "get_agent",
]
