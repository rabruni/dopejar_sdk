"""
platform_sdk.tier0_core.metrics
─────────────────────────────────
Counters, gauges, and histograms with standard naming and labels.
Exports via Prometheus /metrics endpoint or push gateway.

Minimal stack: prometheus-client
Configure via: PLATFORM_METRICS_ENABLED=true|false
               PLATFORM_METRICS_PORT (default: 8001)
"""
from __future__ import annotations

import os
from typing import Callable

from prometheus_client import Counter, Gauge, Histogram, start_http_server

# Standard labels applied to every metric
_DEFAULT_LABELS = ["service", "env"]
_SERVICE = os.getenv("APP_NAME", "platform")
_ENV = os.getenv("APP_ENV", "development")
_DEFAULT_LABEL_VALUES = [_SERVICE, _ENV]


def counter(name: str, description: str, labels: list[str] | None = None) -> Callable:
    """
    Create (or retrieve) a counter with standard platform labels.

    Usage:
        requests_total = counter("http_requests_total", "Total HTTP requests", ["method", "path"])
        requests_total(method="GET", path="/api/users").inc()
    """
    all_labels = _DEFAULT_LABELS + (labels or [])
    c = Counter(name, description, all_labels)

    def _counter(**extra_labels: str) -> Counter:
        return c.labels(*_DEFAULT_LABEL_VALUES, **extra_labels)

    return _counter


def gauge(name: str, description: str, labels: list[str] | None = None) -> Callable:
    """
    Create (or retrieve) a gauge with standard platform labels.

    Usage:
        active_connections = gauge("db_connections_active", "Active DB connections")
        active_connections().set(42)
    """
    all_labels = _DEFAULT_LABELS + (labels or [])
    g = Gauge(name, description, all_labels)

    def _gauge(**extra_labels: str) -> Gauge:
        return g.labels(*_DEFAULT_LABEL_VALUES, **extra_labels)

    return _gauge


def histogram(
    name: str,
    description: str,
    labels: list[str] | None = None,
    buckets: tuple = (0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
) -> Callable:
    """
    Create (or retrieve) a histogram with standard platform labels.

    Usage:
        request_duration = histogram("http_request_duration_seconds", "Request duration")

        import time
        start = time.monotonic()
        # ... handle request ...
        request_duration(method="GET").observe(time.monotonic() - start)
    """
    all_labels = _DEFAULT_LABELS + (labels or [])
    h = Histogram(name, description, all_labels, buckets=buckets)

    def _histogram(**extra_labels: str) -> Histogram:
        return h.labels(*_DEFAULT_LABEL_VALUES, **extra_labels)

    return _histogram


def start_metrics_server(port: int | None = None) -> None:
    """
    Start the Prometheus HTTP metrics server on a dedicated port.
    Call once at application startup.
    """
    port = port or int(os.getenv("PLATFORM_METRICS_PORT", "8001"))
    start_http_server(port)


# ── MCP handler ───────────────────────────────────────────────────────────────

_mcp_metric_fns: dict = {}


async def _mcp_emit_metric(args: dict) -> dict:
    kind = args["kind"]
    metric_name = args["name"]
    value = args.get("value", 1)
    label_dict = args.get("labels") or {}
    label_keys = list(label_dict.keys()) or None

    key = f"{kind}:{metric_name}"
    if key not in _mcp_metric_fns:
        desc = f"MCP {kind}: {metric_name}"
        if kind == "counter":
            _mcp_metric_fns[key] = counter(metric_name, desc, label_keys)
        elif kind == "gauge":
            _mcp_metric_fns[key] = gauge(metric_name, desc, label_keys)
        elif kind == "histogram":
            _mcp_metric_fns[key] = histogram(metric_name, desc, label_keys)

    fn = _mcp_metric_fns.get(key)
    if fn is not None:
        if kind == "counter":
            fn(**label_dict).inc(value)
        elif kind == "gauge":
            fn(**label_dict).set(value)
        elif kind == "histogram":
            fn(**label_dict).observe(value)
    return {"recorded": True, "kind": kind, "name": metric_name}


__sdk_export__ = {
    "surface": "service",
    "exports": ["counter", "gauge", "histogram"],
    "mcp_tools": [
        {
            "name": "emit_metric",
            "description": "Record a platform metric (counter, gauge, or histogram).",
            "schema": {
                "type": "object",
                "properties": {
                    "kind": {
                        "type": "string",
                        "enum": ["counter", "gauge", "histogram"],
                    },
                    "name": {"type": "string"},
                    "value": {"type": "number", "default": 1},
                    "labels": {"type": "object"},
                },
                "required": ["kind", "name"],
            },
            "handler": "_mcp_emit_metric",
        },
    ],
    "description": "Prometheus counters, gauges, and histograms",
    "tier": "tier0_core",
    "module": "metrics",
}
