# platform_sdk Adoption Guide

> How to onboard a service, migrate existing code, and stay compliant with the Platform Contract.

---

## 1. Quick Start

### Install

```bash
# Editable local install (monorepo / single-repo)
pip install -e ./platform_sdk

# Core extras only
pip install -e "./platform_sdk[core]"

# Full stack including GenAI
pip install -e "./platform_sdk[full]"
```

### Minimal wiring (5 minutes)

```python
# In your service's entrypoint (main.py / app.py):
from platform_sdk import get_logger, get_config

log = get_logger()
cfg = get_config()

log.info("service_started", version=cfg.app.version)
```

That's it. You're now emitting structured JSON logs with correlation IDs.

---

## 2. Adoption Checklist

Work through this checklist when onboarding a new service.

### Tier A — Non-Negotiable (Sprint 1)

- [ ] **Logging** — Replace all `print()`, `logging.getLogger()`, and raw `structlog` calls with `from platform_sdk import get_logger`
- [ ] **Errors** — Replace raw `raise Exception(...)` with `from platform_sdk import PlatformError, ValidationError, NotFoundError, ...`
- [ ] **Config** — Replace `os.environ.get(...)` with `from platform_sdk import get_config`
- [ ] **Secrets** — Replace hardcoded secrets and raw `os.environ` secret reads with `from platform_sdk import get_secret`
- [ ] **Identity** — Replace raw JWT decode calls with `from platform_sdk import verify_token, get_principal`
- [ ] **Validation** — Replace manual input validation with `from platform_sdk import validate_input`
- [ ] **Metrics** — Replace raw Prometheus calls with `from platform_sdk import counter, gauge, histogram`
- [ ] **Health** — Expose `/health/live` and `/health/ready` via `from platform_sdk import get_health_checker`
- [ ] **Audit** — Emit audit records for all write operations via `from platform_sdk import audit, AuditRecord`
- [ ] **Authorization** — Replace in-line permission checks with `from platform_sdk import can, require_permission`
- [ ] **Data** — Replace raw SQLAlchemy session creation with `from platform_sdk import get_session`
- [ ] **Context** — Inject `RequestContext` at the request boundary via middleware

### Tier B — Within 2 Sprints

- [ ] **Cache** — Replace ad-hoc caching with `from platform_sdk import get_cache`
- [ ] **Retry** — Wrap unreliable calls with `from platform_sdk import retry_policy`
- [ ] **Rate Limiting** — Protect public endpoints with `from platform_sdk import check_rate_limit`
- [ ] **Notifications** — Replace direct email/SMS calls with `from platform_sdk import send_notification`
- [ ] **Serialization** — Use `from platform_sdk import serialize, deserialize` for wire format

### Tier C — When GenAI Features Are Added

- [ ] **Inference** — Use `from platform_sdk import complete, embed` instead of raw `openai` / `anthropic` calls
- [ ] **LLM Observability** — Wrap all inference calls with `from platform_sdk import observe, record_inference`
- [ ] **Vector Search** — Use `from platform_sdk import vector_search, vector_upsert` for RAG pipelines

---

## 3. Migration Patterns

### Migrating from raw logging

**Before:**
```python
import logging
logger = logging.getLogger(__name__)
logger.info(f"User {user_id} logged in")
```

**After:**
```python
from platform_sdk import get_logger
log = get_logger()
log.info("user_login", user_id=user_id)
```

Benefits: structured JSON, automatic request_id/trace_id injection, redaction of sensitive keys.

---

### Migrating from raw error handling

**Before:**
```python
raise ValueError(f"User {user_id} not found")
raise Exception("Unauthorized")
```

**After:**
```python
from platform_sdk import NotFoundError, AuthError
raise NotFoundError("user", user_id)
raise AuthError("Invalid or expired token")
```

Benefits: stable error codes, consistent HTTP status mapping, Sentry/OTel integration.

---

### Migrating from raw OpenAI calls

**Before:**
```python
from openai import OpenAI
client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
response = client.chat.completions.create(
    model="gpt-4o",
    messages=[{"role": "user", "content": prompt}],
)
text = response.choices[0].message.content
```

**After:**
```python
from platform_sdk import complete, Message
response = await complete([
    Message(role="user", content=prompt),
], model="gpt-4o")
text = response.content
```

Benefits: provider portability (swap to Anthropic/Ollama via env var), automatic observability, cost tracking.

---

## 4. Environment Variables Reference

Set these in `.env` (local) or your deployment secrets manager.

| Variable | Default | Description |
|----------|---------|-------------|
| `PLATFORM_IDENTITY_PROVIDER` | `mock` | `zitadel` \| `auth0` \| `clerk` \| `mock` |
| `PLATFORM_SECRETS_BACKEND` | `env` | `env` \| `infisical` \| `vault` \| `mock` |
| `PLATFORM_ENVIRONMENT` | `local` | `local` \| `test` \| `staging` \| `production` |
| `PLATFORM_SERVICE_NAME` | `unknown` | Your service name (e.g. `api-gateway`) |
| `PLATFORM_LOG_LEVEL` | `INFO` | `DEBUG` \| `INFO` \| `WARNING` \| `ERROR` |
| `PLATFORM_LOG_FORMAT` | `json` | `json` \| `console` |
| `DATABASE_URL` | — | SQLAlchemy async URL |
| `REDIS_URL` | `redis://localhost:6379` | Redis connection string |
| `PLATFORM_AUTHZ_BACKEND` | `simple` | `simple` \| `spicedb` |
| `PLATFORM_NOTIFICATIONS_BACKEND` | `mock` | `mock` \| `novu` \| `smtp` |
| `PLATFORM_VECTOR_BACKEND` | `memory` | `memory` \| `qdrant` |
| `PLATFORM_INFERENCE_PROVIDER` | `mock` | `mock` \| `openai` \| `anthropic` \| `ollama` |
| `PLATFORM_LLM_OBS_BACKEND` | `mock` | `mock` \| `langfuse` |
| `LANGFUSE_PUBLIC_KEY` | — | Required if `PLATFORM_LLM_OBS_BACKEND=langfuse` |
| `LANGFUSE_SECRET_KEY` | — | Required if `PLATFORM_LLM_OBS_BACKEND=langfuse` |

---

## 5. Linting and CI Enforcement

The platform contract is enforced via import-checker linting:

```bash
# Run the import checker (checks for direct imports of underlying libraries)
platform-sdk lint ./src

# Expected output when compliant:
# ✓ No contract violations found in ./src
```

### What the linter checks

Direct imports of libraries that are owned by platform_sdk are flagged:

```python
# VIOLATION — import jwt directly
import jwt                          # use: from platform_sdk import verify_token

# VIOLATION — import structlog directly
import structlog                    # use: from platform_sdk import get_logger

# VIOLATION — import sqlalchemy sessions directly
from sqlalchemy.orm import Session  # use: from platform_sdk import get_session

# VIOLATION — import openai directly
from openai import OpenAI           # use: from platform_sdk import complete
```

Add to your CI pipeline:

```yaml
# .github/workflows/lint.yml
- name: Platform SDK contract check
  run: platform-sdk lint ./src
```

---

## 6. Testing

Run tests with all providers in mock mode (zero external services):

```bash
pip install -e "./platform_sdk[dev]"
pytest platform_sdk/tests/ -v

# Or from your service's test suite:
PLATFORM_INFERENCE_PROVIDER=mock \
PLATFORM_IDENTITY_PROVIDER=mock \
pytest tests/
```

All modules ship with `MockProvider` classes. See `platform_sdk/tests/conftest.py` for the full mock provider setup.

---

## 7. MCP Server (Agent Integration)

If you're using Claude or a Cursor-based agent, expose platform_sdk as MCP tools:

```bash
python -m platform_sdk.mcp_server
```

Or configure in `.claude/config.json`:

```json
{
  "mcpServers": {
    "platform-sdk": {
      "command": "python",
      "args": ["-m", "platform_sdk.mcp_server"],
      "cwd": "/path/to/project"
    }
  }
}
```

The agent can then call `call_inference`, `query_vector`, `log_event`, etc. directly as tools without writing Python.

---

## 8. Getting Help

- **Full module reference:** `MODULES.md`
- **Platform contract:** `docs/CONTRACT.md`
- **Tooling guide:** `docs/TOOLING.md`
- **Source:** `platform_sdk/` (each module has full docstrings)
