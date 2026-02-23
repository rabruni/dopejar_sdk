# Service Surface

The service surface is the full platform import contract for backend services.
It is a strict superset of the [agent surface](agent.md).

```python
from platform_sdk import get_session, verify_token, complete
# or equivalently:
from platform_sdk.service import get_session, verify_token, complete
```

## Everything on the agent surface, plus…

| Concern | Symbols | Module |
|---------|---------|--------|
| **Identity** | `verify_token`, `get_principal`, `Principal` | `tier0_core.identity` |
| **Errors (full)** | `AuthError`, `ValidationError`, `NotFoundError`, `ForbiddenError`, `ConflictError` | `tier0_core.errors` |
| **Config** | `get_config`, `PlatformConfig` | `tier0_core.config` |
| **Secrets** | `get_secret`, `SecretStr` | `tier0_core.secrets` |
| **Data** | `get_session`, `get_engine` | `tier0_core.data` |
| **Metrics** | `counter`, `gauge`, `histogram` | `tier0_core.metrics` |
| **Context** | `get_context`, `set_context`, `RequestContext` | `tier1_runtime.context` |
| **Validation** | `validate_input` | `tier1_runtime.validate` |
| **Serialization** | `serialize`, `deserialize` | `tier1_runtime.serialize` |
| **Retry** | `retry_policy` | `tier1_runtime.retry` |
| **Rate limiting** | `check_rate_limit` | `tier1_runtime.ratelimit` |
| **Middleware** | `PlatformASGIMiddleware`, `PlatformWSGIMiddleware` | `tier1_runtime.middleware` |
| **Health** | `HealthChecker`, `get_health_checker` | `tier2_reliability.health` |
| **Audit** | `audit`, `AuditRecord` | `tier2_reliability.audit` |
| **Cache** | `get_cache` | `tier2_reliability.cache` |
| **Authorization** | `can`, `require_permission` | `tier3_platform.authorization` |
| **Notifications** | `send_notification` | `tier3_platform.notifications` |

## Usage example — FastAPI service

```python
from platform_sdk import (
    verify_token, validate_input, get_session,
    audit, can, send_notification,
    get_logger, PlatformError,
)

log = get_logger(__name__)

@app.post("/orders")
async def create_order(request: Request, body: OrderInput):
    # Auth
    principal = verify_token(request.headers.get("Authorization", ""))

    # Authorization
    require_permission(principal, "order:create", resource="orders")

    # Validation
    validated = validate_input(OrderInput, body.dict())

    # Business logic
    async with get_session() as session:
        order = Order(**validated)
        session.add(order)
        await session.commit()

    # Audit trail
    await audit(principal, "order.create", "order", str(order.id))

    # Notification
    await send_notification(principal.email, "order_confirmation", {"order_id": order.id})

    log.info("order.created", order_id=str(order.id), actor=principal.id)
    return {"id": str(order.id)}
```

## API Reference

Full API reference for each module is in the [API Reference](../api/tier0/identity.md) section.
