"""
platform_sdk.tier4_advanced.llm_obs
─────────────────────────────────────
LLM observability — trace every inference call with token usage, latency,
cost, prompt versions, and quality scores. All data flows to Langfuse (OSS)
for dashboards, debugging, and evaluation pipelines.

Minimal stack: YES (Tier C GenAI)

Environment variables:
  PLATFORM_LLM_OBS_BACKEND      — langfuse | mock (default: mock)
  LANGFUSE_PUBLIC_KEY           — Langfuse project public key
  LANGFUSE_SECRET_KEY           — Langfuse project secret key
  LANGFUSE_HOST                 — Langfuse server URL (default: https://cloud.langfuse.com)
"""
from __future__ import annotations

import os
import time
import uuid
from contextlib import asynccontextmanager, contextmanager
from dataclasses import dataclass, field
from typing import Any, AsyncGenerator, Generator, Protocol, runtime_checkable

from platform_sdk.tier0_core.logging import get_logger
from platform_sdk.tier4_advanced.cost import estimate_llm_cost
from platform_sdk.tier4_advanced.inference import InferenceResponse

logger = get_logger()


# ── Data models ────────────────────────────────────────────────────────────

@dataclass
class TraceSpan:
    trace_id: str
    span_id: str
    name: str
    model: str | None = None
    input: Any = None
    output: Any = None
    usage: dict[str, int] = field(default_factory=dict)
    latency_ms: float = 0.0
    cost_usd: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)
    scores: dict[str, float] = field(default_factory=dict)
    start_time: float = field(default_factory=time.time)
    end_time: float | None = None

    def end(self) -> None:
        self.end_time = time.time()
        self.latency_ms = (self.end_time - self.start_time) * 1000

    def score(self, name: str, value: float) -> None:
        """Attach a quality score (e.g. 'faithfulness': 0.95)."""
        self.scores[name] = value


# ── Protocol ───────────────────────────────────────────────────────────────

@runtime_checkable
class LLMObsProvider(Protocol):
    def create_trace(
        self,
        name: str,
        *,
        trace_id: str | None = None,
        user_id: str | None = None,
        session_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> "LLMTrace": ...

    def flush(self) -> None: ...


class LLMTrace(Protocol):
    def generation(
        self,
        name: str,
        *,
        model: str | None = None,
        input: Any = None,
        output: Any = None,
        usage: dict[str, int] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> TraceSpan: ...

    def score(self, name: str, value: float, comment: str = "") -> None: ...

    def end(self) -> None: ...


# ── Mock provider ──────────────────────────────────────────────────────────

class MockLLMTrace:
    """Collects spans in-memory. Inspect .spans in tests."""

    def __init__(self, name: str, trace_id: str) -> None:
        self.name = name
        self.trace_id = trace_id
        self.spans: list[TraceSpan] = []
        self._scores: dict[str, float] = {}

    def generation(
        self,
        name: str,
        *,
        model: str | None = None,
        input: Any = None,
        output: Any = None,
        usage: dict[str, int] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> TraceSpan:
        u = usage or {}
        cost = estimate_llm_cost(
            model or "",
            prompt_tokens=u.get("prompt_tokens", 0),
            completion_tokens=u.get("completion_tokens", 0),
        )
        span = TraceSpan(
            trace_id=self.trace_id,
            span_id=str(uuid.uuid4()),
            name=name,
            model=model,
            input=input,
            output=output,
            usage=u,
            cost_usd=cost,
            metadata=metadata or {},
        )
        span.end()
        self.spans.append(span)
        return span

    def score(self, name: str, value: float, comment: str = "") -> None:
        self._scores[name] = value

    def end(self) -> None:
        logger.debug(
            "llm_trace_ended",
            trace_id=self.trace_id,
            name=self.name,
            spans=len(self.spans),
        )


class MockLLMObsProvider:
    """In-memory observability. Use PLATFORM_LLM_OBS_BACKEND=mock in tests."""

    def __init__(self) -> None:
        self.traces: list[MockLLMTrace] = []

    def create_trace(
        self,
        name: str,
        *,
        trace_id: str | None = None,
        user_id: str | None = None,
        session_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> MockLLMTrace:
        tid = trace_id or str(uuid.uuid4())
        trace = MockLLMTrace(name=name, trace_id=tid)
        self.traces.append(trace)
        return trace

    def flush(self) -> None:
        pass  # nothing to flush in mock


# ── Langfuse provider ──────────────────────────────────────────────────────

class LangfuseObsProvider:
    """
    Production observability via Langfuse.
    Install: pip install langfuse
    """

    def __init__(self) -> None:
        try:
            from langfuse import Langfuse  # type: ignore[import]
        except ImportError as exc:
            raise ImportError(
                "Install 'langfuse' to use LLM observability: pip install langfuse"
            ) from exc

        public_key = os.environ.get("LANGFUSE_PUBLIC_KEY")
        secret_key = os.environ.get("LANGFUSE_SECRET_KEY")
        host = os.environ.get("LANGFUSE_HOST", "https://cloud.langfuse.com")

        if not public_key or not secret_key:
            raise EnvironmentError(
                "LANGFUSE_PUBLIC_KEY and LANGFUSE_SECRET_KEY must be set "
                "when PLATFORM_LLM_OBS_BACKEND=langfuse"
            )

        from langfuse import Langfuse  # type: ignore[import]
        self._lf = Langfuse(public_key=public_key, secret_key=secret_key, host=host)

    def create_trace(
        self,
        name: str,
        *,
        trace_id: str | None = None,
        user_id: str | None = None,
        session_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> "LangfuseTrace":
        trace = self._lf.trace(
            id=trace_id,
            name=name,
            user_id=user_id,
            session_id=session_id,
            metadata=metadata or {},
        )
        return LangfuseTrace(trace)

    def flush(self) -> None:
        self._lf.flush()


class LangfuseTrace:
    def __init__(self, trace: Any) -> None:
        self._trace = trace

    def generation(
        self,
        name: str,
        *,
        model: str | None = None,
        input: Any = None,
        output: Any = None,
        usage: dict[str, int] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> TraceSpan:
        u = usage or {}
        cost = estimate_llm_cost(
            model or "",
            prompt_tokens=u.get("prompt_tokens", 0),
            completion_tokens=u.get("completion_tokens", 0),
        )
        span_id = str(uuid.uuid4())
        self._trace.generation(
            name=name,
            model=model,
            input=input,
            output=output,
            usage={
                "input": u.get("prompt_tokens", 0),
                "output": u.get("completion_tokens", 0),
                "total": u.get("total_tokens", 0),
            } if u else None,
            metadata={**(metadata or {}), "cost_usd": cost},
        )
        return TraceSpan(
            trace_id=self._trace.id,
            span_id=span_id,
            name=name,
            model=model,
            input=input,
            output=output,
            usage=u,
            cost_usd=cost,
            metadata=metadata or {},
        )

    def score(self, name: str, value: float, comment: str = "") -> None:
        self._trace.score(name=name, value=value, comment=comment)

    def end(self) -> None:
        pass  # Langfuse auto-ends traces on flush


# ── Provider factory ───────────────────────────────────────────────────────

_provider: LLMObsProvider | None = None


def get_provider() -> LLMObsProvider:
    global _provider
    if _provider is not None:
        return _provider

    backend = os.environ.get("PLATFORM_LLM_OBS_BACKEND", "mock").lower()

    if backend == "mock":
        _provider = MockLLMObsProvider()
    elif backend == "langfuse":
        _provider = LangfuseObsProvider()
    else:
        raise ValueError(
            f"Unknown PLATFORM_LLM_OBS_BACKEND: {backend!r}. Supported: mock, langfuse"
        )
    return _provider


# ── Convenience helpers ────────────────────────────────────────────────────

def observe(
    name: str,
    *,
    user_id: str | None = None,
    session_id: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> Any:
    """
    Create a new LLM trace. Returns a trace object; call .end() when done.

    Usage::

        from platform_sdk import observe
        trace = observe("rag-pipeline", user_id="u_123")
        span = trace.generation("retrieve", model="text-embedding-3-small", ...)
        trace.end()
    """
    return get_provider().create_trace(
        name,
        user_id=user_id,
        session_id=session_id,
        metadata=metadata,
    )


def get_llm_tracer() -> LLMObsProvider:
    """Return the configured LLM observability provider."""
    return get_provider()


def record_inference(
    trace_name: str,
    response: InferenceResponse,
    *,
    input_messages: list[Any] | None = None,
    user_id: str | None = None,
) -> TraceSpan:
    """
    Convenience: record a completed inference response to the obs backend.

    Usage::

        from platform_sdk import complete, record_inference
        response = await complete(messages)
        record_inference("chat-turn", response, user_id="u_123")
    """
    trace = get_provider().create_trace(trace_name, user_id=user_id)
    span = trace.generation(
        "llm_call",
        model=response.model,
        input=input_messages,
        output=response.content,
        usage=response.usage,
    )
    trace.end()
    return span


__all__ = [
    "TraceSpan",
    "LLMObsProvider",
    "LLMTrace",
    "MockLLMTrace",
    "MockLLMObsProvider",
    "LangfuseObsProvider",
    "get_provider",
    "observe",
    "get_llm_tracer",
    "record_inference",
]


__sdk_export__ = {
    "surface": "agent",
    "exports": ["observe", "get_llm_tracer", "record_inference"],
    "description": "LLM observability via Langfuse — trace tokens, cost, latency, and quality",
    "tier": "tier4_advanced",
    "module": "llm_obs",
}
