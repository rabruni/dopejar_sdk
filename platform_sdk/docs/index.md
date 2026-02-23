# Platform SDK

Shared platform SDK for all services and AI agents. One import path.
Provider-swappable backends. Zero side-effects at import time.

```python
# Services
from platform_sdk import get_session, verify_token, complete

# Agents — narrower surface, same package
from platform_sdk.agent import complete, vector_search, observe
```

---

## Two-Surface Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        platform_sdk                             │
│                                                                 │
│   ┌───────────────────────────────────────────────────────┐    │
│   │                   service surface                      │    │
│   │  identity · config · secrets · data · metrics         │    │
│   │  context · validate · retry · ratelimit · middleware   │    │
│   │  health · audit · cache · authorization · notify       │    │
│   │                                                         │    │
│   │   ┌─────────────────────────────────────────────┐     │    │
│   │   │              agent surface                   │     │    │
│   │   │  complete · embed · Message                  │     │    │
│   │   │  observe · record_inference · get_llm_tracer │     │    │
│   │   │  vector_search · vector_upsert               │     │    │
│   │   │  get_logger                                  │     │    │
│   │   │  PlatformError · RateLimitError              │     │    │
│   │   └─────────────────────────────────────────────┘     │    │
│   └───────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────┘
```

| Consumer | Import from | Gets |
|----------|-------------|------|
| AI agent | `platform_sdk.agent` | LLM · vector · logging · errors |
| Backend service | `platform_sdk` or `platform_sdk.service` | Everything above + auth, DB, metrics, etc. |

---

## Quick Start

```bash
pip install -e ./platform_sdk
```

```python
# Agents — minimal surface
from platform_sdk.agent import complete, Message, vector_search

response = await complete([
    Message(role="system", content="You are a helpful assistant."),
    Message(role="user", content="What is platform_sdk?"),
])
print(response.content)

# Services — full surface
from platform_sdk import get_session, verify_token, audit
principal = verify_token(request.headers["Authorization"])
```

---

## Provider Selection

All backends are selected via environment variables — no code changes needed:

| Concern | Env var | Options |
|---------|---------|---------|
| Inference | `PLATFORM_INFERENCE_PROVIDER` | `mock` · `openai` · `anthropic` · `ollama` |
| Identity | `PLATFORM_IDENTITY_PROVIDER` | `mock` · `zitadel` · `auth0` |
| Vector store | `PLATFORM_VECTOR_BACKEND` | `memory` · `qdrant` |
| LLM observability | `PLATFORM_LLM_OBS_BACKEND` | `mock` · `langfuse` |
| Secrets | `PLATFORM_SECRETS_BACKEND` | `env` · `mock` · `infisical` |

Default in all cases: `mock` — no external services required for local dev or CI.

---

## MCP Server

Expose the SDK as tools for Claude and other MCP-compatible agents:

```bash
python -m platform_sdk.mcp_server
```

Tools are discovered automatically from `__sdk_export__` on each module.
No `mcp_server.py` edits needed when adding new capabilities.

---

## Learn More

- [Agent Surface](surfaces/agent.md) — what agents can call
- [Service Surface](surfaces/service.md) — full contract for backend services
- [Adding a Module](guides/adding-a-module.md) — ≤5 steps
- [Platform Contract](CONTRACT.md) — the one enforced rule
- [Adoption Guide](ADOPTION.md) — migration patterns
