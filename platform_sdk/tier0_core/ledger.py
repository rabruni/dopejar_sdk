"""
platform_sdk.tier0_core.ledger
───────────────────────────────
Cryptographic ledger database for tamper-evident conversation logging.

Every entry is SHA-256 chained to the previous — the digest of turn N is
derived from the digest of turn N-1. Any retroactive modification to a
historical turn breaks the chain from that point forward and is immediately
detectable via ``verify_chain()``.

Backends: immudb (self-hosted) | qldb (AWS managed) | mock (tests/local)
Select via: PLATFORM_LEDGER_BACKEND=mock|immudb|qldb
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import os
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable


# ── Domain model ─────────────────────────────────────────────────────────────

@dataclass
class LedgerEntry:
    """
    A single immutable conversation turn on the ledger.

    ``digest`` is the SHA-256 of the entry's canonical form (including
    ``prev_digest``). Verifying the full chain means re-computing every
    digest from the genesis entry forward.
    """
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: float = field(default_factory=time.time)
    conversation_id: str = ""
    turn_index: int = 0               # monotonically increasing per conversation
    role: str = ""                    # "user" | "assistant" | "system" | "tool"
    content: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    prev_digest: str = ""             # digest of the previous entry (empty for genesis)
    digest: str = ""                  # SHA-256 of this entry's canonical form

    def is_genesis(self) -> bool:
        """True if this is the first turn in the conversation."""
        return self.turn_index == 0 and self.prev_digest == ""


def _compute_digest(entry: LedgerEntry) -> str:
    """Derive the SHA-256 digest for an entry from its canonical fields."""
    canonical = json.dumps(
        {
            "prev_digest": entry.prev_digest,
            "conversation_id": entry.conversation_id,
            "turn_index": entry.turn_index,
            "role": entry.role,
            "content": entry.content,
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    return hashlib.sha256(canonical).hexdigest()


# ── Provider protocol ─────────────────────────────────────────────────────────

@runtime_checkable
class LedgerProvider(Protocol):
    """Implement this protocol to add a new ledger backend."""

    async def append(self, entry: LedgerEntry) -> LedgerEntry:
        """
        Append an entry. Sets ``turn_index``, ``prev_digest``, and ``digest``
        before writing. Returns the entry with all fields populated.
        """
        ...

    async def get_entry(self, conversation_id: str, turn_index: int) -> LedgerEntry | None:
        """Retrieve a specific turn by conversation ID and turn index."""
        ...

    async def get_conversation(
        self,
        conversation_id: str,
        limit: int = 100,
        offset: int = 0,
    ) -> list[LedgerEntry]:
        """Return all entries for a conversation in turn order."""
        ...

    async def verify_chain(self, conversation_id: str) -> tuple[bool, str]:
        """
        Verify the hash chain for a conversation.

        Returns:
            ``(True, "ok")`` if the chain is intact.
            ``(False, reason)`` if any entry fails verification.
        """
        ...


# ── Mock provider (tests / local dev) ─────────────────────────────────────────

class MockLedgerProvider:
    """
    In-memory hash-chained ledger — suitable for tests and local dev.
    Fully implements the cryptographic chain with no external dependencies.
    """

    def __init__(self) -> None:
        # conversation_id → list of LedgerEntry in turn order
        self._store: dict[str, list[LedgerEntry]] = {}

    async def append(self, entry: LedgerEntry) -> LedgerEntry:
        turns = self._store.setdefault(entry.conversation_id, [])
        if turns:
            last = turns[-1]
            entry.turn_index = last.turn_index + 1
            entry.prev_digest = last.digest
        else:
            entry.turn_index = 0
            entry.prev_digest = ""

        entry.digest = _compute_digest(entry)
        turns.append(entry)
        return entry

    async def get_entry(self, conversation_id: str, turn_index: int) -> LedgerEntry | None:
        turns = self._store.get(conversation_id, [])
        if 0 <= turn_index < len(turns):
            return turns[turn_index]
        return None

    async def get_conversation(
        self,
        conversation_id: str,
        limit: int = 100,
        offset: int = 0,
    ) -> list[LedgerEntry]:
        turns = self._store.get(conversation_id, [])
        return turns[offset: offset + limit]

    async def verify_chain(self, conversation_id: str) -> tuple[bool, str]:
        turns = self._store.get(conversation_id, [])
        if not turns:
            return True, "ok"

        for i, entry in enumerate(turns):
            expected = _compute_digest(entry)
            if entry.digest != expected:
                return False, f"turn {i}: digest mismatch"
            if i > 0 and entry.prev_digest != turns[i - 1].digest:
                return False, f"turn {i}: prev_digest chain broken"

        return True, "ok"


# ── immudb provider ───────────────────────────────────────────────────────────

class ImmudbProvider:
    """
    immudb cryptographic ledger backend (self-hosted).

    immudb writes are natively tamper-evident via Merkle tree. This provider
    adds application-level SHA-256 chaining on top for end-to-end verifiability
    without trusting the immudb node.

    Requires: IMMUDB_HOST, IMMUDB_PORT, IMMUDB_USERNAME, IMMUDB_PASSWORD
    Optional: IMMUDB_DATABASE (default: defaultdb)
    Install:  pip install immudb-py
    """

    def __init__(self) -> None:
        from immudb import ImmudbClient  # type: ignore[import]
        from immudb.datatypesv2 import DatabaseSettingsV2  # type: ignore[import]

        host = os.getenv("IMMUDB_HOST", "localhost")
        port = int(os.getenv("IMMUDB_PORT", "3322"))
        username = os.getenv("IMMUDB_USERNAME", "immudb")
        password = os.getenv("IMMUDB_PASSWORD", "immudb")
        database = os.getenv("IMMUDB_DATABASE", "defaultdb")

        self._client = ImmudbClient(f"{host}:{port}")
        self._client.login(username, password)
        if database != "defaultdb":
            try:
                self._client.createDatabaseV2(
                    database, settings=DatabaseSettingsV2(), ifNotExists=True,
                )
            except Exception:
                pass  # Older immudb versions or database already exists
        self._client.useDatabase(database.encode())

    def _entry_key(self, conversation_id: str, turn_index: int) -> bytes:
        return f"conv:{conversation_id}:{turn_index:08d}".encode()

    def _head_key(self, conversation_id: str) -> bytes:
        return f"conv:{conversation_id}:__head__".encode()

    def _sync_append(self, entry: LedgerEntry) -> LedgerEntry:
        head_key = self._head_key(entry.conversation_id)
        try:
            raw = self._client.get(head_key)
            head = json.loads(raw.value)
            entry.turn_index = head["turn_index"] + 1
            entry.prev_digest = head["digest"]
        except Exception:
            entry.turn_index = 0
            entry.prev_digest = ""

        entry.digest = _compute_digest(entry)
        key = self._entry_key(entry.conversation_id, entry.turn_index)
        self._client.set(key, json.dumps(_entry_to_dict(entry)).encode())
        self._client.set(
            head_key,
            json.dumps({"turn_index": entry.turn_index, "digest": entry.digest}).encode(),
        )
        return entry

    async def append(self, entry: LedgerEntry) -> LedgerEntry:
        return await asyncio.to_thread(self._sync_append, entry)

    def _sync_get_entry(self, conversation_id: str, turn_index: int) -> LedgerEntry | None:
        key = self._entry_key(conversation_id, turn_index)
        try:
            raw = self._client.get(key)
            return _entry_from_dict(json.loads(raw.value))
        except Exception:
            return None

    async def get_entry(self, conversation_id: str, turn_index: int) -> LedgerEntry | None:
        return await asyncio.to_thread(self._sync_get_entry, conversation_id, turn_index)

    async def get_conversation(
        self,
        conversation_id: str,
        limit: int = 100,
        offset: int = 0,
    ) -> list[LedgerEntry]:
        results: list[LedgerEntry] = []
        for i in range(offset, offset + limit):
            entry = await self.get_entry(conversation_id, i)
            if entry is None:
                break
            results.append(entry)
        return results

    async def verify_chain(self, conversation_id: str) -> tuple[bool, str]:
        entries = await self.get_conversation(conversation_id, limit=10_000)
        if not entries:
            return True, "ok"
        for i, entry in enumerate(entries):
            expected = _compute_digest(entry)
            if entry.digest != expected:
                return False, f"turn {i}: digest mismatch"
            if i > 0 and entry.prev_digest != entries[i - 1].digest:
                return False, f"turn {i}: chain broken at prev_digest"
        return True, "ok"


# ── QLDB provider ─────────────────────────────────────────────────────────────

class QLDBProvider:
    """
    Amazon QLDB cryptographic ledger backend (managed).

    QLDB natively maintains an immutable, cryptographically verifiable journal.
    This provider adds application-level SHA-256 chaining consistent with
    MockLedgerProvider and ImmudbProvider for cross-backend portability.

    Requires: AWS credentials in environment, QLDB_LEDGER_NAME
    Install:  pip install pyqldb
    """

    def __init__(self) -> None:
        from pyqldb.driver.qldb_driver import QldbDriver  # type: ignore[import]

        ledger_name = os.environ["QLDB_LEDGER_NAME"]
        self._driver = QldbDriver(ledger_name=ledger_name)

    def _sync_append(self, entry: LedgerEntry) -> LedgerEntry:
        def _txn(txn: Any) -> None:
            cursor = txn.execute_statement(
                "SELECT turn_index, digest FROM conversation_head WHERE conversation_id = ?",
                entry.conversation_id,
            )
            rows = list(cursor)
            if rows:
                entry.turn_index = int(rows[0]["turn_index"]) + 1
                entry.prev_digest = str(rows[0]["digest"])
            else:
                entry.turn_index = 0
                entry.prev_digest = ""

            entry.digest = _compute_digest(entry)
            d = _entry_to_dict(entry)
            txn.execute_statement(
                "INSERT INTO conversation_turns VALUE "
                "{'id': ?, 'conversation_id': ?, 'turn_index': ?, 'role': ?, "
                "'content': ?, 'timestamp': ?, 'prev_digest': ?, 'digest': ?, 'metadata': ?}",
                d["id"], d["conversation_id"], d["turn_index"],
                d["role"], d["content"], d["timestamp"],
                d["prev_digest"], d["digest"], json.dumps(d["metadata"]),
            )
            if rows:
                txn.execute_statement(
                    "UPDATE conversation_head SET turn_index = ?, digest = ? "
                    "WHERE conversation_id = ?",
                    entry.turn_index, entry.digest, entry.conversation_id,
                )
            else:
                txn.execute_statement(
                    "INSERT INTO conversation_head VALUE "
                    "{'conversation_id': ?, 'turn_index': ?, 'digest': ?}",
                    entry.conversation_id, entry.turn_index, entry.digest,
                )

        self._driver.execute_lambda(_txn)
        return entry

    async def append(self, entry: LedgerEntry) -> LedgerEntry:
        return await asyncio.to_thread(self._sync_append, entry)

    def _sync_get_entry(self, conversation_id: str, turn_index: int) -> LedgerEntry | None:
        def _txn(txn: Any) -> Any:
            cursor = txn.execute_statement(
                "SELECT * FROM conversation_turns "
                "WHERE conversation_id = ? AND turn_index = ?",
                conversation_id, turn_index,
            )
            rows = list(cursor)
            return rows[0] if rows else None

        row = self._driver.execute_lambda(_txn)
        if row is None:
            return None
        return _entry_from_dict({k: row[k] for k in row.keys()})

    async def get_entry(self, conversation_id: str, turn_index: int) -> LedgerEntry | None:
        return await asyncio.to_thread(self._sync_get_entry, conversation_id, turn_index)

    def _sync_get_conversation(
        self, conversation_id: str, limit: int, offset: int
    ) -> list[LedgerEntry]:
        def _txn(txn: Any) -> list[Any]:
            cursor = txn.execute_statement(
                "SELECT * FROM conversation_turns WHERE conversation_id = ? "
                "ORDER BY turn_index",
                conversation_id,
            )
            return list(cursor)

        rows = self._driver.execute_lambda(_txn)
        entries = [_entry_from_dict({k: r[k] for k in r.keys()}) for r in rows]
        return entries[offset: offset + limit]

    async def get_conversation(
        self,
        conversation_id: str,
        limit: int = 100,
        offset: int = 0,
    ) -> list[LedgerEntry]:
        return await asyncio.to_thread(self._sync_get_conversation, conversation_id, limit, offset)

    async def verify_chain(self, conversation_id: str) -> tuple[bool, str]:
        entries = await self.get_conversation(conversation_id, limit=10_000)
        if not entries:
            return True, "ok"
        for i, entry in enumerate(entries):
            expected = _compute_digest(entry)
            if entry.digest != expected:
                return False, f"turn {i}: digest mismatch"
            if i > 0 and entry.prev_digest != entries[i - 1].digest:
                return False, f"turn {i}: chain broken at prev_digest"
        return True, "ok"


# ── Serialization helpers ─────────────────────────────────────────────────────

def _entry_to_dict(entry: LedgerEntry) -> dict[str, Any]:
    return {
        "id": entry.id,
        "timestamp": entry.timestamp,
        "conversation_id": entry.conversation_id,
        "turn_index": entry.turn_index,
        "role": entry.role,
        "content": entry.content,
        "metadata": entry.metadata,
        "prev_digest": entry.prev_digest,
        "digest": entry.digest,
    }


def _entry_from_dict(d: dict[str, Any]) -> LedgerEntry:
    return LedgerEntry(
        id=d.get("id", str(uuid.uuid4())),
        timestamp=float(d.get("timestamp", time.time())),
        conversation_id=d.get("conversation_id", ""),
        turn_index=int(d.get("turn_index", 0)),
        role=d.get("role", ""),
        content=d.get("content", ""),
        metadata=d.get("metadata", {}),
        prev_digest=d.get("prev_digest", ""),
        digest=d.get("digest", ""),
    )


# ── Provider factory ──────────────────────────────────────────────────────────

_provider: LedgerProvider | None = None


def _build_provider() -> LedgerProvider:
    name = os.getenv("PLATFORM_LEDGER_BACKEND", "mock").lower()
    if name == "mock":
        return MockLedgerProvider()
    if name == "immudb":
        return ImmudbProvider()
    if name == "qldb":
        return QLDBProvider()
    raise EnvironmentError(
        f"Unknown PLATFORM_LEDGER_BACKEND={name!r}. "
        "Valid options: mock, immudb, qldb"
    )


def get_provider() -> LedgerProvider:
    global _provider
    if _provider is None:
        _provider = _build_provider()
    return _provider


def _reset_provider() -> None:
    """For tests — reset provider so env changes take effect."""
    global _provider
    _provider = None


# ── Public API ────────────────────────────────────────────────────────────────

async def append_turn(
    conversation_id: str,
    role: str,
    content: str,
    metadata: dict[str, Any] | None = None,
) -> LedgerEntry:
    """
    Append a conversation turn to the cryptographic ledger.

    Each turn is SHA-256 chained to the previous, making the conversation
    history tamper-evident. Any modification to a historical turn invalidates
    the chain from that point forward.

    Args:
        conversation_id: Unique identifier for the conversation.
        role: Speaker role — ``"user"``, ``"assistant"``, ``"system"``, or ``"tool"``.
        content: The message content.
        metadata: Optional structured metadata (model, tokens, latency, etc.).

    Returns:
        The written ``LedgerEntry`` with ``turn_index``, ``prev_digest``, and
        ``digest`` all populated.

    Usage::

        entry = await append_turn(
            conversation_id="conv-abc123",
            role="user",
            content="What is the capital of France?",
        )
        reply = await append_turn(
            conversation_id="conv-abc123",
            role="assistant",
            content="Paris.",
            metadata={"model": "gpt-4o", "input_tokens": 12, "output_tokens": 3},
        )
    """
    entry = LedgerEntry(
        conversation_id=conversation_id,
        role=role,
        content=content,
        metadata=metadata or {},
    )
    return await get_provider().append(entry)


async def get_conversation(
    conversation_id: str,
    limit: int = 100,
    offset: int = 0,
) -> list[LedgerEntry]:
    """
    Return all turns for a conversation in chronological order.

    Args:
        conversation_id: The conversation to retrieve.
        limit: Maximum number of turns to return (default 100).
        offset: Skip this many turns from the start (for pagination).

    Returns:
        List of ``LedgerEntry`` objects in turn order.
    """
    return await get_provider().get_conversation(
        conversation_id, limit=limit, offset=offset
    )


async def verify_chain(conversation_id: str) -> tuple[bool, str]:
    """
    Verify the cryptographic hash chain for a conversation.

    Re-computes the SHA-256 digest for every turn and confirms each entry's
    ``prev_digest`` matches the preceding entry's ``digest``.

    Returns:
        ``(True, "ok")`` if the chain is intact.
        ``(False, reason)`` if any entry has been tampered with.

    Usage::

        ok, reason = await verify_chain("conv-abc123")
        if not ok:
            raise IntegrityError(f"Ledger chain broken: {reason}")
    """
    return await get_provider().verify_chain(conversation_id)


# ── MCP handler ───────────────────────────────────────────────────────────────

async def _mcp_append_turn(args: dict) -> dict:
    entry = await append_turn(
        conversation_id=args["conversation_id"],
        role=args["role"],
        content=args["content"],
        metadata=args.get("metadata"),
    )
    return {
        "id": entry.id,
        "conversation_id": entry.conversation_id,
        "turn_index": entry.turn_index,
        "digest": entry.digest,
    }


__sdk_export__ = {
    "surface": "service",
    "exports": ["append_turn", "get_conversation", "verify_chain", "LedgerEntry"],
    "mcp_tools": [
        {
            "name": "append_turn",
            "description": "Append a conversation turn to the cryptographic ledger (SHA-256 chained).",
            "schema": {
                "type": "object",
                "properties": {
                    "conversation_id": {"type": "string"},
                    "role": {
                        "type": "string",
                        "enum": ["user", "assistant", "system", "tool"],
                    },
                    "content": {"type": "string"},
                    "metadata": {"type": "object"},
                },
                "required": ["conversation_id", "role", "content"],
            },
            "handler": "_mcp_append_turn",
        },
    ],
    "description": "Cryptographic ledger DB for tamper-evident conversation logging (immudb, QLDB, mock)",
    "tier": "tier0_core",
    "module": "ledger",
}
