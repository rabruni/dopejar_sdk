# Platform SDK Contract

> **Version:** 1.0
> **Status:** Enforced

---

## The Rule

> Any concern covered by `platform_sdk` **must** be satisfied through `platform_sdk`.
> No app, service, or agent may re-implement these concerns directly.

This is not a suggestion. It is the architectural contract that keeps the platform coherent,
auditable, and maintainable as the system grows and agents write more of the code.

---

## Covered Concerns (you may not bypass these)

| Concern | Module | What you must NOT do instead |
|---------|--------|------------------------------|
| Authentication | `platform_sdk.tier0_core.identity` | Import `jwt`, `python-jose`, provider SDKs directly |
| Logging | `platform_sdk.tier0_core.logging` | Use `print()`, `logging.getLogger()` directly, raw structlog |
| Error capture | `platform_sdk.tier0_core.errors` | Import `sentry_sdk` directly; raise raw `Exception` |
| Configuration | `platform_sdk.tier0_core.config` | Scatter `os.getenv()` calls; use raw `.env` reading |
| Secrets | `platform_sdk.tier0_core.secrets` | Use `os.getenv()` for secrets; hardcode in source |
| Database access | `platform_sdk.tier0_core.data` | Import `sqlalchemy` directly; open raw connections |
| Input validation | `platform_sdk.tier1_runtime.validate` | Use Pydantic directly in routes without going through validate |
| Request context | `platform_sdk.tier1_runtime.context` | Use `threading.local()` or ad-hoc request globals |
| Health checks | `platform_sdk.tier2_reliability.health` | Write custom /health endpoints per service |
| Audit trail | `platform_sdk.tier2_reliability.audit` | Write custom audit log tables per service |
| Permissions | `platform_sdk.tier3_platform.authorization` | Use `if user.role == "admin"` inline in business logic |
| Notifications | `platform_sdk.tier3_platform.notifications` | Import `smtplib`, `boto3.ses`, notification SDKs directly |
| LLM inference | `platform_sdk.tier4_advanced.inference` | Import `openai`, `anthropic`, `litellm` directly |
| LLM observability | `platform_sdk.tier4_advanced.llm_obs` | Skip observability; use provider dashboards only |
| Vector search | `platform_sdk.tier3_platform.vector` | Import `qdrant_client`, `pinecone` directly |

---

## Why This Exists

When agents write code — and this system is designed so agents write most of the code —
they will naturally reach for the simplest tool available. Without a contract, every agent
makes a different choice:

- One agent uses `print()` for logging
- Another imports `openai` directly
- Another rolls its own JWT verification
- Another hardcodes a secret in a config file

Each bypass is invisible individually. At scale, they become:
- Security vulnerabilities (raw secrets, unverified tokens)
- Compliance gaps (missing audit trails, unredacted PII in logs)
- Runaway costs (direct LLM calls with no cost tracking or rate limiting)
- Operational nightmares (10 different logging formats, no correlation IDs)

The contract prevents this by making `platform_sdk` the single, well-audited path.

---

## What Agents Must Do

When an agent writes code in this system, it must:

1. **Check `MODULES.md` first** — before reaching for any external library, check whether
   the concern is already covered by a `platform_sdk` module.

2. **Import from `platform_sdk`** — not from the underlying library directly.
   ```python
   # ✓ correct
   from platform_sdk import get_logger, complete, verify_token

   # ✗ wrong — bypasses the contract
   import structlog
   import openai
   import jwt
   ```

3. **Use `MockProvider` in tests** — never spin up real services in unit tests.
   ```python
   # ✓ correct — uses built-in mock
   os.environ["PLATFORM_INFERENCE_PROVIDER"] = "mock"

   # ✗ wrong — calls real OpenAI in unit tests
   ```

4. **Never add a secret to source code** — use `get_secret("key_name")` always.

5. **Never silence errors** — let `platform_sdk.errors` capture and report them.

---

## Enforcement

**Linting (CI):** An import-checker rule flags any direct import of underlying libraries
that are covered by the SDK. The following imports fail CI in app/service code:

```
import jwt          → use platform_sdk.tier0_core.identity
import structlog    → use platform_sdk.tier0_core.logging
import openai       → use platform_sdk.tier4_advanced.inference
import anthropic    → use platform_sdk.tier4_advanced.inference
import litellm      → use platform_sdk.tier4_advanced.inference
import sentry_sdk   → use platform_sdk.tier0_core.errors
import sqlalchemy   → use platform_sdk.tier0_core.data
import qdrant_client → use platform_sdk.tier3_platform.vector
import langfuse     → use platform_sdk.tier4_advanced.llm_obs
```

**Exception:** These imports are allowed **inside `platform_sdk` itself** (the implementations).
Nowhere else.

**Agent system prompt:** This document is referenced in every agent's system prompt.
Agents are instructed: "Before writing any code, consult `platform_sdk/docs/CONTRACT.md`."

---

## Deferred Modules

Modules marked `DEFERRED` in `MODULES.md` are not yet implemented. When a new concern
arises that a deferred module would cover:

1. Implement the module in `platform_sdk` (or stub it with the Protocol)
2. Update `MODULES.md` status from `DEFERRED` to `YES`
3. Then use it from app/service code

Do **not** implement the concern in app code and defer the SDK module indefinitely.
The bypass always becomes permanent.

---

## Amendments

This contract is amended by updating this file via pull request with at least one
review from the platform team. Adding a new covered concern requires:

1. The module must be implemented (or stubbed) in `platform_sdk`
2. `MODULES.md` must be updated
3. `ADOPTION.md` must be updated with migration guidance
