"""
platform_sdk.tier3_platform.notifications
────────────────────────────────────────────
Multi-channel notification delivery — email, SMS, push, in-app, Slack, webhook.
Template management and delivery tracking via Novu.

Minimal stack: Novu (OSS, MIT, 37k+ stars) | SMTP fallback
Configure via: PLATFORM_NOTIFICATIONS_BACKEND=novu|smtp|mock
               NOVU_API_KEY, NOVU_API_URL (default: https://api.novu.co)
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any

from platform_sdk.tier0_core.identity import Principal


@dataclass
class NotificationResult:
    success: bool
    notification_id: str | None = None
    channel: str = "unknown"
    error: str | None = None


# ── Mock provider ─────────────────────────────────────────────────────────────

class MockNotificationsProvider:
    sent: list[dict] = []

    async def send(
        self,
        recipient: Principal | str,
        template: str,
        channel: str,
        data: dict,
    ) -> NotificationResult:
        record = {
            "recipient": recipient.id if isinstance(recipient, Principal) else recipient,
            "template": template,
            "channel": channel,
            "data": data,
        }
        MockNotificationsProvider.sent.append(record)
        return NotificationResult(
            success=True,
            notification_id=f"mock-{len(MockNotificationsProvider.sent)}",
            channel=channel,
        )


# ── Novu provider ─────────────────────────────────────────────────────────────

class NovuProvider:
    """
    Novu multi-channel notifications.
    Requires: NOVU_API_KEY
    Optional: NOVU_API_URL (default: https://api.novu.co)
    """

    def __init__(self) -> None:
        import httpx
        self._api_key = os.environ["NOVU_API_KEY"]
        self._base_url = os.getenv("NOVU_API_URL", "https://api.novu.co")
        self._client = httpx.AsyncClient(
            base_url=self._base_url,
            headers={
                "Authorization": f"ApiKey {self._api_key}",
                "Content-Type": "application/json",
            },
            timeout=10.0,
        )

    async def send(
        self,
        recipient: Principal | str,
        template: str,
        channel: str,
        data: dict,
    ) -> NotificationResult:
        recipient_id = recipient.id if isinstance(recipient, Principal) else recipient
        email = recipient.email if isinstance(recipient, Principal) else None

        payload: dict[str, Any] = {
            "name": template,
            "to": {"subscriberId": recipient_id},
            "payload": data,
        }
        if email:
            payload["to"]["email"] = email

        resp = await self._client.post("/v1/events/trigger", json=payload)

        if resp.status_code not in (200, 201):
            return NotificationResult(
                success=False,
                channel=channel,
                error=f"Novu API error: {resp.status_code} {resp.text}",
            )

        result = resp.json()
        return NotificationResult(
            success=True,
            notification_id=result.get("data", {}).get("transactionId"),
            channel=channel,
        )


# ── SMTP provider (email-only fallback) ───────────────────────────────────────

class SmtpProvider:
    """
    Simple SMTP email provider. Email-only — no SMS/push/in-app.
    Requires: SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, SMTP_FROM
    """

    def __init__(self) -> None:
        self._host = os.environ["SMTP_HOST"]
        self._port = int(os.getenv("SMTP_PORT", "587"))
        self._user = os.environ["SMTP_USER"]
        self._password = os.environ["SMTP_PASSWORD"]
        self._from_addr = os.environ["SMTP_FROM"]

    async def send(
        self,
        recipient: Principal | str,
        template: str,
        channel: str,
        data: dict,
    ) -> NotificationResult:
        import smtplib
        from email.mime.text import MIMEText
        from email.mime.multipart import MIMEMultipart

        to_email = recipient.email if isinstance(recipient, Principal) else recipient

        msg = MIMEMultipart("alternative")
        msg["Subject"] = data.get("subject", template)
        msg["From"] = self._from_addr
        msg["To"] = to_email

        body = data.get("body", f"Notification: {template}")
        msg.attach(MIMEText(body, "plain"))

        try:
            with smtplib.SMTP(self._host, self._port) as server:
                server.starttls()
                server.login(self._user, self._password)
                server.sendmail(self._from_addr, [to_email], msg.as_string())
            return NotificationResult(success=True, channel="email")
        except Exception as exc:
            return NotificationResult(success=False, channel="email", error=str(exc))


# ── Provider registry ─────────────────────────────────────────────────────────

_provider = None


def _build_provider():
    name = os.getenv("PLATFORM_NOTIFICATIONS_BACKEND", "mock").lower()
    if name == "mock":
        return MockNotificationsProvider()
    if name == "novu":
        return NovuProvider()
    if name == "smtp":
        return SmtpProvider()
    raise EnvironmentError(f"Unknown PLATFORM_NOTIFICATIONS_BACKEND={name!r}.")


def get_provider():
    global _provider
    if _provider is None:
        _provider = _build_provider()
    return _provider


def _reset_provider() -> None:
    global _provider
    _provider = None


# ── Public API ────────────────────────────────────────────────────────────────

async def send_notification(
    recipient: Principal | str,
    template: str,
    channel: str = "email",
    data: dict | None = None,
) -> NotificationResult:
    """
    Send a notification via the configured provider.

    Args:
        recipient: Principal or subscriber ID string.
        template:  Template name in Novu (or subject for SMTP).
        channel:   "email" | "sms" | "push" | "in_app" | "slack"
        data:      Template variables / payload.

    Usage:
        await send_notification(
            recipient=principal,
            template="order_confirmed",
            channel="email",
            data={"order_id": "ord_123", "total": "$49.99"},
        )
    """
    return await get_provider().send(recipient, template, channel, data or {})


__sdk_export__ = {
    "surface": "service",
    "exports": ["send_notification"],
    "description": "Multi-channel notifications via Novu (email, SMS, push, Slack, in-app)",
    "tier": "tier3_platform",
    "module": "notifications",
}
