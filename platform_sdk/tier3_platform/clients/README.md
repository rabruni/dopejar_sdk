# platform_sdk.tier3_platform.clients

This directory contains **pre-built API client wrappers** for common third-party services.
Each client is a thin wrapper around `platform_sdk.tier3_platform.api_client.ApiClient` that
adds service-specific auth, endpoint mapping, and error translation.

## Available Clients

| Client | Status | Provider |
|--------|--------|----------|
| `stripe.py` | DEFERRED | Stripe Payments |
| `sendgrid.py` | DEFERRED | SendGrid Email |
| `twilio.py` | DEFERRED | Twilio SMS |
| `github.py` | DEFERRED | GitHub API |
| `slack.py` | DEFERRED | Slack Webhooks |

## Adding a New Client

1. Create `platform_sdk/tier3_platform/clients/<service>.py`
2. Extend `ApiClient` or compose it
3. Inject auth via `platform_sdk.tier0_core.secrets.get_secret()`
4. Map service errors to `platform_sdk.tier0_core.errors.UpstreamError`
5. Export from this package's `__init__.py`

## Example

```python
from platform_sdk.tier3_platform.api_client import ApiClient
from platform_sdk.tier0_core.secrets import get_secret

class StripeClient(ApiClient):
    def __init__(self) -> None:
        super().__init__(base_url="https://api.stripe.com/v1", service_name="stripe")
        self._api_key = get_secret("STRIPE_SECRET_KEY")

    async def create_customer(self, email: str) -> dict:
        return await self.post("/customers", json={"email": email})
```
