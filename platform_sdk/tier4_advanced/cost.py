"""
platform_sdk.tier4_advanced.cost
───────────────────────────────────
Usage metering, budget enforcement, and unit economics attribution.
Tracks LLM token spend, API call volume, and storage usage per
tenant/feature/agent and surfaces real-time cost against budgets.

Minimal stack: DEFERRED — add when per-tenant billing or cost attribution
is required.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any


# ── LLM token pricing table (USD per 1K tokens) ────────────────────────────
# Approximate prices — update as providers change their rates.

_MODEL_PRICES: dict[str, dict[str, float]] = {
    "gpt-4o": {"input": 0.0025, "output": 0.010},
    "gpt-4o-mini": {"input": 0.00015, "output": 0.0006},
    "claude-opus-4-6": {"input": 0.015, "output": 0.075},
    "claude-sonnet-4-6": {"input": 0.003, "output": 0.015},
    "claude-haiku-4-5-20251001": {"input": 0.00025, "output": 0.00125},
    "text-embedding-3-small": {"input": 0.00002, "output": 0.0},
    "text-embedding-3-large": {"input": 0.00013, "output": 0.0},
}


def estimate_llm_cost(
    model: str,
    prompt_tokens: int,
    completion_tokens: int,
) -> float:
    """
    Estimate the USD cost of an LLM call.

    Returns 0.0 if the model is not in the pricing table.
    """
    prices = _MODEL_PRICES.get(model, _MODEL_PRICES.get(model.split("/")[-1], {}))
    if not prices:
        return 0.0
    return (
        (prompt_tokens / 1000) * prices.get("input", 0.0)
        + (completion_tokens / 1000) * prices.get("output", 0.0)
    )


# ── Usage ledger ───────────────────────────────────────────────────────────

@dataclass
class UsageEntry:
    org_id: str
    feature: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    cost_usd: float
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class BudgetStatus:
    org_id: str
    feature: str | None
    budget_usd: float
    spent_usd: float
    remaining_usd: float
    exceeded: bool

    @property
    def utilization_pct(self) -> float:
        if self.budget_usd == 0:
            return 0.0
        return round((self.spent_usd / self.budget_usd) * 100, 2)


class UsageLedger:
    """
    In-memory usage ledger. Replace with TimescaleDB / ClickHouse in production.
    """

    def __init__(self) -> None:
        self._entries: list[UsageEntry] = []
        self._budgets: dict[tuple[str, str | None], float] = {}

    def record(self, entry: UsageEntry) -> None:
        """Record a usage entry."""
        self._entries.append(entry)

    def record_llm(
        self,
        org_id: str,
        feature: str,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
        **metadata: Any,
    ) -> UsageEntry:
        """Record an LLM call with auto-calculated cost."""
        cost = estimate_llm_cost(model, prompt_tokens, completion_tokens)
        entry = UsageEntry(
            org_id=org_id,
            feature=feature,
            model=model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            cost_usd=cost,
            metadata=dict(metadata),
        )
        self.record(entry)
        return entry

    def set_budget(self, org_id: str, budget_usd: float, feature: str | None = None) -> None:
        """Set a spend budget for an org (optionally scoped to a feature)."""
        self._budgets[(org_id, feature)] = budget_usd

    def get_spent(self, org_id: str, feature: str | None = None) -> float:
        """Return total USD spent by org (and optionally feature)."""
        return sum(
            e.cost_usd
            for e in self._entries
            if e.org_id == org_id and (feature is None or e.feature == feature)
        )

    def check_budget(self, org_id: str, feature: str | None = None) -> BudgetStatus:
        """Return budget status for an org."""
        budget = self._budgets.get((org_id, feature), float("inf"))
        spent = self.get_spent(org_id, feature)
        return BudgetStatus(
            org_id=org_id,
            feature=feature,
            budget_usd=budget,
            spent_usd=spent,
            remaining_usd=max(budget - spent, 0.0),
            exceeded=spent > budget,
        )


_ledger: UsageLedger | None = None


def get_ledger() -> UsageLedger:
    global _ledger
    if _ledger is None:
        _ledger = UsageLedger()
    return _ledger


__all__ = [
    "estimate_llm_cost",
    "UsageEntry",
    "BudgetStatus",
    "UsageLedger",
    "get_ledger",
    "_MODEL_PRICES",
]
