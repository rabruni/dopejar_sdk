"""
platform_sdk.tier3_platform.experiments
─────────────────────────────────────────
A/B testing and multi-variate experiment framework. Assigns users to
experiment variants deterministically (same user always gets same variant),
tracks exposure events, and rolls up conversion metrics.

Backed by: GrowthBook (OSS), Statsig (enterprise), or env-var mock.

Minimal stack: DEFERRED — add when product requires data-driven feature
experimentation.
"""
from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable


@dataclass
class Variant:
    key: str
    weight: float  # 0.0–1.0; all variants in an experiment should sum to 1.0
    payload: dict[str, Any] | None = None


@dataclass
class ExperimentResult:
    experiment_key: str
    variant: Variant
    in_experiment: bool


@runtime_checkable
class ExperimentsProvider(Protocol):
    def get_variant(
        self,
        experiment_key: str,
        user_id: str,
        variants: list[Variant],
        *,
        attributes: dict[str, Any] | None = None,
    ) -> ExperimentResult: ...


class HashExperimentsProvider:
    """
    Deterministic bucketing via SHA-256 hash of (experiment_key, user_id).
    Requires no external service — works entirely in-process.
    """

    def get_variant(
        self,
        experiment_key: str,
        user_id: str,
        variants: list[Variant],
        *,
        attributes: dict[str, Any] | None = None,
    ) -> ExperimentResult:
        if not variants:
            raise ValueError("At least one variant is required")

        # Deterministic float in [0, 1) from hash
        h = hashlib.sha256(f"{experiment_key}:{user_id}".encode()).hexdigest()
        bucket = int(h[:8], 16) / 0xFFFFFFFF

        cumulative = 0.0
        for variant in variants:
            cumulative += variant.weight
            if bucket < cumulative:
                return ExperimentResult(
                    experiment_key=experiment_key,
                    variant=variant,
                    in_experiment=True,
                )

        # Fallback: last variant (handles floating point edge cases)
        return ExperimentResult(
            experiment_key=experiment_key,
            variant=variants[-1],
            in_experiment=True,
        )


class MockExperimentsProvider:
    """Always returns the first variant — useful for deterministic tests."""

    def get_variant(
        self,
        experiment_key: str,
        user_id: str,
        variants: list[Variant],
        *,
        attributes: dict[str, Any] | None = None,
    ) -> ExperimentResult:
        if not variants:
            raise ValueError("At least one variant is required")
        return ExperimentResult(
            experiment_key=experiment_key,
            variant=variants[0],
            in_experiment=True,
        )


_provider: ExperimentsProvider | None = None


def get_provider() -> ExperimentsProvider:
    global _provider
    if _provider is not None:
        return _provider

    backend = os.environ.get("PLATFORM_EXPERIMENTS_BACKEND", "hash").lower()
    if backend == "hash":
        _provider = HashExperimentsProvider()
    elif backend == "mock":
        _provider = MockExperimentsProvider()
    else:
        _provider = HashExperimentsProvider()
    return _provider


def get_variant(
    experiment_key: str,
    user_id: str,
    variants: list[Variant],
    *,
    attributes: dict[str, Any] | None = None,
) -> ExperimentResult:
    return get_provider().get_variant(experiment_key, user_id, variants, attributes=attributes)


__all__ = [
    "Variant", "ExperimentResult", "ExperimentsProvider",
    "HashExperimentsProvider", "MockExperimentsProvider",
    "get_provider", "get_variant",
]
