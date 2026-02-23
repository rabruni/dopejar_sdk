# platform-sdk

> Every cross-cutting concern, one place. No app or agent re-implements these.

The `platform_sdk` is the shared foundation for all services and agents in this system.
It provides 20 production-ready modules covering identity, logging, errors, data access,
authorization, notifications, and GenAI capabilities — all provider-abstracted so the
backing tool can change without touching call sites.

See [`MODULES.md`](MODULES.md) for the complete reference of all 44 modules.
See [`docs/CONTRACT.md`](docs/CONTRACT.md) for the enforcement rule.

---

## Install

```bash
# Editable local install (recommended during development)
pip install -e ./platform_sdk[core,genai]

# Core only (no GenAI)
pip install -e ./platform_sdk[core]

# Everything
pip install -e ./platform_sdk[full]
```

---

## Quick Start

```python
from platform_sdk import (
    get_logger,
    get_config,
    get_secret,
    verify_token,
    get_session,
    validate_input,
    audit,
    can,
    send_notification,
    complete,        # LLM inference
    observe,         # LLM observability
    vector_search,   # vector/RAG
)

# Logging — structured, context-aware, redacted automatically
log = get_logger(__name__)
log.info("user.login", user_id="u_123", provider="github")

# Config — typed, env-layered
config = get_config()
db_url = config.database_url          # typed field, raises at startup if missing

# Secrets — wrapped in SecretStr, never logged
api_key = get_secret("stripe_api_key")

# Identity — verify any token, get normalized Principal
principal = verify_token(request.headers["Authorization"])
# principal.id, principal.org_id, principal.roles

# Data — transactional session
async with get_session() as session:
    result = await session.execute(select(User).where(User.id == principal.id))

# Validation — Pydantic v2, raises platform ValidationError
class CreateOrder(BaseModel):
    item_id: str
    quantity: int

order = validate_input(CreateOrder, request.json())

# Audit — compliance trail
await audit(
    actor=principal,
    action="order.create",
    resource_type="order",
    resource_id=order.id,
    outcome="success",
)

# Authorization — who can do X on Y
if not await can(principal, "order:cancel", f"order:{order.id}"):
    raise AuthError("not_authorized")

# Notifications — multi-channel
await send_notification(
    recipient=principal,
    template="order_confirmed",
    channel="email",
    data={"order_id": order.id},
)

# LLM inference — provider-abstracted, cost-tracked
response = await complete(
    messages=[{"role": "user", "content": "Summarize this order."}],
    model="gpt-4o-mini",   # or "claude-3-haiku" or "ollama/llama3.2"
)

# Vector search (RAG)
results = await vector_search(
    collection="knowledge_base",
    query="return policy for digital goods",
    top_k=5,
)
```

---

## Provider Selection

Every module reads its backend from an environment variable. No code changes to swap providers.

```bash
# Identity
PLATFORM_IDENTITY_PROVIDER=zitadel   # zitadel | auth0 | clerk | mock
ZITADEL_DOMAIN=your-org.zitadel.cloud
ZITADEL_CLIENT_ID=...

# Secrets
PLATFORM_SECRETS_BACKEND=infisical   # infisical | vault | env | mock
INFISICAL_TOKEN=...

# Database
DATABASE_URL=postgresql+asyncpg://user:pass@localhost/db

# Cache / Rate limiting
REDIS_URL=redis://localhost:6379

# LLM
PLATFORM_INFERENCE_PROVIDER=openai   # openai | anthropic | ollama | mock
OPENAI_API_KEY=...

# LLM Observability
LANGFUSE_SECRET_KEY=...
LANGFUSE_PUBLIC_KEY=...
LANGFUSE_HOST=https://cloud.langfuse.com   # or self-hosted

# Vector store
PLATFORM_VECTOR_BACKEND=qdrant        # qdrant | memory | mock
QDRANT_URL=http://localhost:6333

# Notifications
PLATFORM_NOTIFICATIONS_BACKEND=novu   # novu | smtp | mock
NOVU_API_KEY=...

# Authorization
PLATFORM_AUTHZ_BACKEND=simple         # simple | spicedb | mock
SPICEDB_ENDPOINT=localhost:50051
SPICEDB_API_KEY=...
```

---

## For Agents

Agents interact with the SDK in two ways:

**1. Python imports** (when writing service code):
```python
from platform_sdk import get_logger, complete, vector_search
```

**2. MCP tools** (when Claude/Cursor acts as an agent):
```bash
# Start the MCP server
platform-sdk-mcp

# Or in mcp settings:
# command: platform-sdk-mcp
```
The MCP server exposes `platform_log`, `platform_validate`, `platform_verify_token`,
`platform_audit`, `platform_call_inference`, `platform_vector_search`, and more as
structured tool calls.

---

## Module Tiers

| Tier | Purpose | Modules |
|------|---------|---------|
| `tier0_core` | Foundational — zero circular deps | identity, logging, errors, config, secrets, data, metrics, tracing, flags, tasks, http, ids, redact |
| `tier1_runtime` | Request-level safety | context, validate, serialize, retry, ratelimit, clock, runtime, middleware |
| `tier2_reliability` | Production operations | health, audit, cache, circuit, storage, crypto, fallback |
| `tier3_platform` | Cross-service patterns | authorization, notifications, vector, api_client, discovery, policy, experiments, agent, multi_tenancy |
| `tier4_advanced` | Add when needed | workflow, messaging, schemas, inference, llm_obs, evals, cost |

**Tier dependency rule:** tier0 imports nothing from tier1+. tier1 imports only tier0. Strictly enforced.

---

## Testing

```bash
# Run all tests
pytest

# Run with mock providers (no external services needed)
PLATFORM_IDENTITY_PROVIDER=mock \
PLATFORM_SECRETS_BACKEND=mock \
PLATFORM_VECTOR_BACKEND=memory \
PLATFORM_INFERENCE_PROVIDER=mock \
pytest
```

Every module ships a `MockProvider` usable in tests with no external services.

---

## Documentation

```bash
# Serve local docs (API reference auto-generated from docstrings)
pip install -e ".[dev]"
mkdocs serve -f platform_sdk/docs/mkdocs.yml
```
