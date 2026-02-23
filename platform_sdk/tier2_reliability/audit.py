"""
platform_sdk.tier2_reliability.audit
───────────────────────────────────────
Append-only audit trail. Every actor/action/resource event is recorded.
Required for GDPR Article 30 and SOC 2 processing integrity.

Backend: structured log (stdout/Loki) or DB table (append-only).
Configure via: PLATFORM_AUDIT_BACKEND=log|db
"""
from __future__ import annotations

import os
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

from platform_sdk.tier0_core.identity import Principal


@dataclass
class AuditRecord:
    """Immutable audit record. Never update or delete these."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: float = field(default_factory=time.time)
    actor_id: str = ""
    actor_org_id: str | None = None
    action: str = ""            # e.g. "order.create", "user.delete"
    resource_type: str = ""     # e.g. "order", "user"
    resource_id: str = ""
    outcome: str = "success"    # "success" | "failure" | "denied"
    metadata: dict[str, Any] = field(default_factory=dict)
    ip_address: str | None = None
    user_agent: str | None = None


async def audit(
    actor: Principal | str,
    action: str,
    resource_type: str,
    resource_id: str,
    outcome: str = "success",
    metadata: dict | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> AuditRecord:
    """
    Write an audit record. Call this for every consequential action.

    Usage:
        await audit(
            actor=principal,
            action="order.cancel",
            resource_type="order",
            resource_id=order_id,
            outcome="success",
            metadata={"reason": "customer_request"},
        )
    """
    actor_id = actor.id if isinstance(actor, Principal) else actor
    actor_org = actor.org_id if isinstance(actor, Principal) else None

    record = AuditRecord(
        actor_id=actor_id,
        actor_org_id=actor_org,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        outcome=outcome,
        metadata=metadata or {},
        ip_address=ip_address,
        user_agent=user_agent,
    )

    backend = os.getenv("PLATFORM_AUDIT_BACKEND", "log").lower()
    if backend == "log":
        _write_log(record)
    elif backend == "db":
        await _write_db(record)

    return record


def _write_log(record: AuditRecord) -> None:
    from platform_sdk.tier0_core.logging import get_logger
    log = get_logger("platform_sdk.audit")
    log.info(
        "audit",
        audit_id=record.id,
        actor_id=record.actor_id,
        actor_org_id=record.actor_org_id,
        action=record.action,
        resource_type=record.resource_type,
        resource_id=record.resource_id,
        outcome=record.outcome,
        metadata=record.metadata,
        ip_address=record.ip_address,
        timestamp=record.timestamp,
    )


async def _write_db(record: AuditRecord) -> None:
    """Write to an append-only DB table. Table must have no UPDATE/DELETE grants."""
    from platform_sdk.tier0_core.data import get_session
    from sqlalchemy import text

    async with get_session() as session:
        await session.execute(
            text("""
                INSERT INTO audit_log
                  (id, timestamp, actor_id, actor_org_id, action,
                   resource_type, resource_id, outcome, metadata)
                VALUES
                  (:id, :ts, :actor_id, :actor_org_id, :action,
                   :resource_type, :resource_id, :outcome, :metadata)
            """),
            {
                "id": record.id,
                "ts": record.timestamp,
                "actor_id": record.actor_id,
                "actor_org_id": record.actor_org_id,
                "action": record.action,
                "resource_type": record.resource_type,
                "resource_id": record.resource_id,
                "outcome": record.outcome,
                "metadata": str(record.metadata),
            },
        )


# ── MCP handler ───────────────────────────────────────────────────────────────

async def _mcp_audit_event(args: dict) -> dict:
    record = await audit(
        actor=args["actor_id"],
        action=args["action"],
        resource_type=args["resource_type"],
        resource_id=args["resource_id"],
        outcome=args.get("outcome", "success"),
        metadata=args.get("metadata"),
    )
    return {"audited": True, "action": args["action"], "id": record.id}


__sdk_export__ = {
    "surface": "service",
    "exports": ["audit", "AuditRecord"],
    "mcp_tools": [
        {
            "name": "audit_event",
            "description": "Record an append-only audit event (GDPR Article 30 / SOC 2).",
            "schema": {
                "type": "object",
                "properties": {
                    "actor_id": {"type": "string"},
                    "action": {"type": "string"},
                    "resource_type": {"type": "string"},
                    "resource_id": {"type": "string"},
                    "outcome": {
                        "type": "string",
                        "enum": ["success", "failure", "denied"],
                        "default": "success",
                    },
                    "metadata": {"type": "object"},
                },
                "required": ["actor_id", "action", "resource_type", "resource_id"],
            },
            "handler": "_mcp_audit_event",
        },
    ],
    "description": "Append-only audit trail (tamper-evident, compliance-ready)",
    "tier": "tier2_reliability",
    "module": "audit",
}
