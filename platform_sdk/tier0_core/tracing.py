"""
platform_sdk.tier0_core.tracing
─────────────────────────────────
Distributed tracing via OpenTelemetry. Provides span creation, context
propagation, and auto-instrumentation helpers. All services should use
these wrappers instead of calling OTel directly so the exporter can be
swapped without changing application code.

Backends: OTLP (gRPC/HTTP), Jaeger, Zipkin, or stdout (dev).

Minimal stack: DEFERRED — add when distributed tracing across ≥2 services
is required.
"""
from __future__ import annotations

import functools
import os
from contextlib import contextmanager
from typing import Any, Callable, Generator, TypeVar

F = TypeVar("F", bound=Callable[..., Any])

_tracer: Any = None


def _get_tracer() -> Any:
    """Lazy-load an OTel tracer. Falls back to a no-op tracer if OTel is not installed."""
    global _tracer
    if _tracer is not None:
        return _tracer
    try:
        from opentelemetry import trace  # type: ignore[import]
        from opentelemetry.sdk.trace import TracerProvider  # type: ignore[import]
        from opentelemetry.sdk.trace.export import BatchSpanProcessor  # type: ignore[import]

        endpoint = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT")
        provider = TracerProvider()

        if endpoint:
            try:
                from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (  # type: ignore[import]
                    OTLPSpanExporter,
                )
                provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))
            except ImportError:
                pass  # OTLP exporter not installed — use no-op

        trace.set_tracer_provider(provider)
        _tracer = trace.get_tracer("platform_sdk")
    except ImportError:
        _tracer = _NoopTracer()

    return _tracer


# ── No-op tracer (used when opentelemetry-sdk is not installed) ───────────

class _NoopSpan:
    def __enter__(self) -> "_NoopSpan":
        return self

    def __exit__(self, *args: Any) -> None:
        pass

    def set_attribute(self, key: str, value: Any) -> None:
        pass

    def record_exception(self, exc: Exception) -> None:
        pass

    def set_status(self, status: Any) -> None:
        pass


class _NoopTracer:
    def start_as_current_span(self, name: str, **kwargs: Any) -> Any:
        return _NoopSpan()

    def start_span(self, name: str, **kwargs: Any) -> _NoopSpan:
        return _NoopSpan()


# ── Public API ─────────────────────────────────────────────────────────────

@contextmanager
def span(name: str, **attributes: Any) -> Generator[Any, None, None]:
    """
    Context manager that wraps a block in an OTel span.

    Usage::

        with span("my_operation", user_id="123") as s:
            result = do_work()
    """
    tracer = _get_tracer()
    with tracer.start_as_current_span(name) as s:
        for k, v in attributes.items():
            try:
                s.set_attribute(k, v)
            except Exception:
                pass
        try:
            yield s
        except Exception as exc:
            try:
                s.record_exception(exc)
            except Exception:
                pass
            raise


def traced(name: str | None = None, **attributes: Any) -> Callable[[F], F]:
    """
    Decorator that wraps a function in an OTel span.

    Usage::

        @traced("my_operation", component="auth")
        def verify(token: str) -> Principal: ...
    """
    def decorator(fn: F) -> F:
        span_name = name or fn.__qualname__

        @functools.wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            with span(span_name, **attributes):
                return fn(*args, **kwargs)

        return wrapper  # type: ignore[return-value]

    return decorator


def get_current_span() -> Any:
    """Return the active span, or a no-op span if tracing is not configured."""
    try:
        from opentelemetry import trace  # type: ignore[import]
        return trace.get_current_span()
    except ImportError:
        return _NoopSpan()


__all__ = ["span", "traced", "get_current_span"]
