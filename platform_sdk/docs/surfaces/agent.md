# Agent Surface

The agent surface is the intentionally narrow import contract for AI agents,
autonomous tools, and MCP clients.

```python
from platform_sdk.agent import complete, vector_search, observe, get_logger
```

## What's included

| Symbol | Module | Purpose |
|--------|--------|---------|
| `complete` | `tier4_advanced.inference` | Call the LLM |
| `embed` | `tier4_advanced.inference` | Get embedding vectors |
| `Message` | `tier4_advanced.inference` | Message dataclass |
| `observe` | `tier4_advanced.llm_obs` | Create an LLM trace |
| `get_llm_tracer` | `tier4_advanced.llm_obs` | Get the obs provider |
| `record_inference` | `tier4_advanced.llm_obs` | Record a completed call |
| `vector_search` | `tier3_platform.vector` | Similarity search |
| `vector_upsert` | `tier3_platform.vector` | Store a vector |
| `vector_delete` | `tier3_platform.vector` | Delete a vector |
| `get_logger` | `tier0_core.logging` | Structured logger |
| `PlatformError` | `tier0_core.errors` | Base error to catch |
| `RateLimitError` | `tier0_core.errors` | Quota exceeded |
| `UpstreamError` | `tier0_core.errors` | Upstream service failure |

## What's NOT included (by design)

```python
from platform_sdk.agent import get_session     # ImportError — boundary enforced
from platform_sdk.agent import verify_token    # ImportError — boundary enforced
from platform_sdk.agent import counter         # ImportError — boundary enforced
```

Agents don't own data, don't authenticate users, and don't manage infrastructure.
Those concerns belong to the service that hosts the agent.

## Usage example

```python
from platform_sdk.agent import complete, Message, vector_search, observe

async def answer_question(question: str, user_id: str) -> str:
    # 1. Retrieve relevant context
    results = await vector_search("knowledge_base", query_vector=[...], top_k=5)
    context = "\n".join(r.payload.get("text", "") for r in results)

    # 2. Call LLM with observability
    trace = observe("qa-pipeline", user_id=user_id)
    response = await complete([
        Message(role="system", content=f"Context:\n{context}"),
        Message(role="user", content=question),
    ])
    trace.end()

    return response.content
```

## API Reference

::: platform_sdk.tier4_advanced.inference
    options:
      members: [complete, embed, Message]

::: platform_sdk.tier4_advanced.llm_obs
    options:
      members: [observe, get_llm_tracer, record_inference]

::: platform_sdk.tier3_platform.vector
    options:
      members: [vector_search, vector_upsert, vector_delete]

::: platform_sdk.tier0_core.logging
    options:
      members: [get_logger]
