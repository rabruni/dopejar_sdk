"""
platform_sdk.tier2_reliability.health
────────────────────────────────────────
Liveness/readiness endpoints with dependency checks.
Required by Kubernetes, ECS, and load balancers.

Usage:
    checker = get_health_checker()
    checker.register("database", check_db, critical=True)
    checker.register("redis", check_redis, critical=False)

    # In FastAPI / Starlette:
    @app.get("/health/live")
    async def liveness():
        return checker.liveness()

    @app.get("/health/ready")
    async def readiness():
        result = await checker.readiness()
        status_code = 200 if result["status"] == "ok" else 503
        return JSONResponse(result, status_code=status_code)
"""
from __future__ import annotations

import asyncio
import time
from collections.abc import Callable, Coroutine
from dataclasses import dataclass, field
from typing import Any


@dataclass
class CheckResult:
    name: str
    status: str           # "ok" | "degraded" | "failed"
    critical: bool
    latency_ms: float
    detail: str | None = None


class HealthChecker:
    def __init__(self) -> None:
        self._checks: list[dict[str, Any]] = []

    def register(
        self,
        name: str,
        check_fn: Callable[[], Coroutine | bool],
        critical: bool = True,
        timeout: float = 5.0,
    ) -> None:
        """
        Register a health check.

        Args:
            name:       Check name (e.g. "database", "redis").
            check_fn:   Async or sync callable. Return True = healthy, raise/False = unhealthy.
            critical:   If True, failure blocks readiness. If False, degraded but not blocking.
            timeout:    Max seconds before the check is considered failed.
        """
        self._checks.append(
            {"name": name, "fn": check_fn, "critical": critical, "timeout": timeout}
        )

    def liveness(self) -> dict:
        """Always returns 200 OK if the process is alive."""
        return {"status": "ok", "timestamp": time.time()}

    async def readiness(self) -> dict:
        """
        Runs all registered checks. Returns 200 if all critical checks pass.
        Returns 503 with check detail if any critical check fails.
        """
        results: list[CheckResult] = []

        for check in self._checks:
            start = time.monotonic()
            try:
                fn = check["fn"]
                if asyncio.iscoroutinefunction(fn):
                    ok = await asyncio.wait_for(fn(), timeout=check["timeout"])
                else:
                    ok = fn()
                status = "ok" if ok else "failed"
                detail = None
            except asyncio.TimeoutError:
                status = "failed"
                detail = f"Timed out after {check['timeout']}s"
            except Exception as exc:
                status = "failed"
                detail = str(exc)

            results.append(CheckResult(
                name=check["name"],
                status=status,
                critical=check["critical"],
                latency_ms=round((time.monotonic() - start) * 1000, 2),
                detail=detail,
            ))

        all_critical_ok = all(
            r.status == "ok" for r in results if r.critical
        )

        return {
            "status": "ok" if all_critical_ok else "degraded",
            "checks": [
                {
                    "name": r.name,
                    "status": r.status,
                    "critical": r.critical,
                    "latency_ms": r.latency_ms,
                    **({"detail": r.detail} if r.detail else {}),
                }
                for r in results
            ],
            "timestamp": time.time(),
        }


# ── Singleton registry ────────────────────────────────────────────────────────

_checker: HealthChecker | None = None


def get_health_checker() -> HealthChecker:
    global _checker
    if _checker is None:
        _checker = HealthChecker()
    return _checker


def _reset_health_checker() -> None:
    global _checker
    _checker = None
