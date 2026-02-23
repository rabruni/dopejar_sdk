"""
platform_sdk.tier4_advanced.inference
───────────────────────────────────────
Unified LLM inference client backed by LiteLLM. Provides a single
call interface for 100+ models (OpenAI, Anthropic, Mistral, Ollama, etc.)
with automatic provider routing, retry, cost tracking, and context injection.

Minimal stack: YES (Tier C GenAI)

Environment variables:
  PLATFORM_INFERENCE_PROVIDER   — openai | anthropic | ollama | mock (default: mock)
  PLATFORM_INFERENCE_MODEL      — default model name (e.g. "gpt-4o", "claude-opus-4-6")
  OPENAI_API_KEY                — if using OpenAI
  ANTHROPIC_API_KEY             — if using Anthropic
  OLLAMA_BASE_URL               — if using local Ollama (default: http://localhost:11434)
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Protocol, runtime_checkable

from platform_sdk.tier0_core.errors import ConfigurationError, UpstreamError
from platform_sdk.tier0_core.logging import get_logger

logger = get_logger()


# ── Data models ────────────────────────────────────────────────────────────

@dataclass
class Message:
    role: str  # system | user | assistant | tool
    content: str
    name: str | None = None
    tool_call_id: str | None = None


@dataclass
class InferenceRequest:
    messages: list[Message]
    model: str | None = None           # overrides PLATFORM_INFERENCE_MODEL
    max_tokens: int = 1024
    temperature: float = 0.7
    stream: bool = False
    tools: list[dict[str, Any]] | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class InferenceResponse:
    content: str
    model: str
    usage: dict[str, int] = field(default_factory=dict)  # prompt_tokens, completion_tokens, total_tokens
    finish_reason: str = "stop"
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def prompt_tokens(self) -> int:
        return self.usage.get("prompt_tokens", 0)

    @property
    def completion_tokens(self) -> int:
        return self.usage.get("completion_tokens", 0)

    @property
    def total_tokens(self) -> int:
        return self.usage.get("total_tokens", 0)


# ── Protocol ───────────────────────────────────────────────────────────────

@runtime_checkable
class InferenceProvider(Protocol):
    async def complete(self, request: InferenceRequest) -> InferenceResponse: ...
    async def embed(self, texts: list[str], model: str | None = None) -> list[list[float]]: ...


# ── Mock provider (zero deps, fast, deterministic) ─────────────────────────

class MockInferenceProvider:
    """
    Returns deterministic mock responses. No API calls made.
    Use PLATFORM_INFERENCE_PROVIDER=mock in tests.
    """

    def __init__(
        self,
        response: str = "Mock response from platform_sdk inference.",
        embedding_dim: int = 1536,
    ) -> None:
        self._response = response
        self._embedding_dim = embedding_dim

    async def complete(self, request: InferenceRequest) -> InferenceResponse:
        prompt_tokens = sum(len(m.content.split()) for m in request.messages)
        completion_tokens = len(self._response.split())
        logger.debug(
            "mock_inference_complete",
            model=request.model or "mock",
            prompt_tokens=prompt_tokens,
        )
        return InferenceResponse(
            content=self._response,
            model=request.model or "mock-model",
            usage={
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": prompt_tokens + completion_tokens,
            },
            finish_reason="stop",
        )

    async def embed(self, texts: list[str], model: str | None = None) -> list[list[float]]:
        import math
        return [
            [math.sin(i * 0.1 + j) for j in range(self._embedding_dim)]
            for i, _ in enumerate(texts)
        ]


# ── LiteLLM provider (100+ models) ────────────────────────────────────────

class LiteLLMProvider:
    """
    Production provider backed by LiteLLM.
    Supports: OpenAI, Anthropic, Cohere, Mistral, Ollama, Azure, Bedrock, etc.

    Install: pip install litellm
    """

    def __init__(self, default_model: str | None = None) -> None:
        self._default_model = (
            default_model
            or os.environ.get("PLATFORM_INFERENCE_MODEL", "gpt-4o-mini")
        )
        try:
            import litellm  # type: ignore[import]
            self._litellm = litellm
            # Suppress verbose LiteLLM logs unless debug is enabled
            if os.environ.get("PLATFORM_LOG_LEVEL", "INFO").upper() != "DEBUG":
                import logging as _logging
                _logging.getLogger("LiteLLM").setLevel(_logging.WARNING)
        except ImportError as exc:
            raise ImportError(
                "Install 'litellm' to use LiteLLM inference provider: pip install litellm"
            ) from exc

    async def complete(self, request: InferenceRequest) -> InferenceResponse:
        model = request.model or self._default_model
        messages = [{"role": m.role, "content": m.content} for m in request.messages]

        kwargs: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "max_tokens": request.max_tokens,
            "temperature": request.temperature,
        }
        if request.tools:
            kwargs["tools"] = request.tools

        try:
            response = await self._litellm.acompletion(**kwargs)
        except Exception as exc:
            raise UpstreamError(
                f"LiteLLM inference failed: {exc}",
                upstream_service="litellm",
            ) from exc

        choice = response.choices[0]
        content = choice.message.content or ""
        tool_calls = []
        if hasattr(choice.message, "tool_calls") and choice.message.tool_calls:
            tool_calls = [
                {
                    "id": tc.id,
                    "type": tc.type,
                    "function": {"name": tc.function.name, "arguments": tc.function.arguments},
                }
                for tc in choice.message.tool_calls
            ]

        usage = {}
        if hasattr(response, "usage") and response.usage:
            usage = {
                "prompt_tokens": getattr(response.usage, "prompt_tokens", 0),
                "completion_tokens": getattr(response.usage, "completion_tokens", 0),
                "total_tokens": getattr(response.usage, "total_tokens", 0),
            }

        logger.info(
            "inference_complete",
            model=model,
            prompt_tokens=usage.get("prompt_tokens", 0),
            completion_tokens=usage.get("completion_tokens", 0),
        )

        return InferenceResponse(
            content=content,
            model=model,
            usage=usage,
            finish_reason=choice.finish_reason or "stop",
            tool_calls=tool_calls,
        )

    async def embed(self, texts: list[str], model: str | None = None) -> list[list[float]]:
        embed_model = model or os.environ.get(
            "PLATFORM_EMBEDDING_MODEL", "text-embedding-3-small"
        )
        try:
            response = await self._litellm.aembedding(model=embed_model, input=texts)
            return [item["embedding"] for item in response["data"]]
        except Exception as exc:
            raise UpstreamError(
                f"LiteLLM embedding failed: {exc}",
                upstream_service="litellm",
            ) from exc


# ── Provider factory ───────────────────────────────────────────────────────

_provider: InferenceProvider | None = None


def get_provider() -> InferenceProvider:
    global _provider
    if _provider is not None:
        return _provider

    backend = os.environ.get("PLATFORM_INFERENCE_PROVIDER", "mock").lower()

    if backend == "mock":
        _provider = MockInferenceProvider()
    elif backend in ("openai", "anthropic", "ollama", "azure", "bedrock", "litellm"):
        _provider = LiteLLMProvider()
    else:
        raise ConfigurationError(
            f"Unknown PLATFORM_INFERENCE_PROVIDER: {backend!r}. "
            "Supported: mock, openai, anthropic, ollama, azure, bedrock, litellm"
        )
    return _provider


# ── Public API ─────────────────────────────────────────────────────────────

async def complete(
    messages: list[Message] | list[dict[str, str]],
    *,
    model: str | None = None,
    max_tokens: int = 1024,
    temperature: float = 0.7,
    tools: list[dict[str, Any]] | None = None,
    **metadata: Any,
) -> InferenceResponse:
    """
    Call the LLM and return a complete response.

    Usage::

        from platform_sdk import complete, Message
        response = await complete([
            Message(role="system", content="You are a helpful assistant."),
            Message(role="user", content="Explain platform_sdk in one sentence."),
        ])
        print(response.content)
    """
    # Normalise dict messages
    normalised: list[Message] = []
    for m in messages:
        if isinstance(m, dict):
            normalised.append(Message(**m))
        else:
            normalised.append(m)

    request = InferenceRequest(
        messages=normalised,
        model=model,
        max_tokens=max_tokens,
        temperature=temperature,
        tools=tools,
        metadata=dict(metadata),
    )
    return await get_provider().complete(request)


async def embed(
    texts: list[str] | str,
    *,
    model: str | None = None,
) -> list[list[float]]:
    """
    Embed text(s) and return a list of embedding vectors.

    Usage::

        from platform_sdk import embed
        vectors = await embed(["hello world", "foo bar"])
    """
    if isinstance(texts, str):
        texts = [texts]
    return await get_provider().embed(texts, model=model)


__all__ = [
    "Message",
    "InferenceRequest",
    "InferenceResponse",
    "InferenceProvider",
    "MockInferenceProvider",
    "LiteLLMProvider",
    "get_provider",
    "complete",
    "embed",
]


# ── MCP handlers ──────────────────────────────────────────────────────────────

async def _mcp_call_inference(args: dict) -> dict:
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


async def _mcp_embed_text(args: dict) -> dict:
    vectors = await embed(args["texts"], model=args.get("model"))
    return {
        "embeddings": vectors,
        "count": len(vectors),
        "dim": len(vectors[0]) if vectors else 0,
    }


__sdk_export__ = {
    "surface": "agent",
    "exports": ["complete", "embed", "Message"],
    "mcp_tools": [
        {
            "name": "call_inference",
            "description": "Call the configured LLM with a list of messages.",
            "schema": {
                "type": "object",
                "properties": {
                    "messages": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "role": {
                                    "type": "string",
                                    "enum": ["system", "user", "assistant"],
                                },
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
            "handler": "_mcp_call_inference",
        },
        {
            "name": "embed_text",
            "description": "Embed text(s) into vectors using the configured embedding model.",
            "schema": {
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
            "handler": "_mcp_embed_text",
        },
    ],
    "description": "LLM inference via LiteLLM (100+ models: OpenAI, Anthropic, Ollama, etc.)",
    "tier": "tier4_advanced",
    "module": "inference",
}
