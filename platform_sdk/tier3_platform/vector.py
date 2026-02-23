"""
platform_sdk.tier3_platform.vector
────────────────────────────────────
Vector store abstraction for embeddings and RAG.
Similarity search with metadata filtering; index lifecycle management.

Minimal stack: Qdrant (prod) | in-memory (dev/test)
Configure via: PLATFORM_VECTOR_BACKEND=qdrant|memory|mock
               QDRANT_URL (default: http://localhost:6333)
               QDRANT_API_KEY (optional)
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any


@dataclass
class VectorSearchResult:
    id: str
    score: float
    payload: dict[str, Any] = field(default_factory=dict)
    vector: list[float] | None = None


# ── In-memory provider (dev / tests) ─────────────────────────────────────────

class MemoryVectorProvider:
    """Brute-force cosine similarity in memory. For development only."""

    def __init__(self) -> None:
        self._collections: dict[str, list[dict]] = {}

    def _cosine(self, a: list[float], b: list[float]) -> float:
        dot = sum(x * y for x, y in zip(a, b))
        norm_a = sum(x ** 2 for x in a) ** 0.5
        norm_b = sum(x ** 2 for x in b) ** 0.5
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot / (norm_a * norm_b)

    async def upsert(
        self, collection: str, id: str, vector: list[float], payload: dict
    ) -> None:
        col = self._collections.setdefault(collection, [])
        for item in col:
            if item["id"] == id:
                item["vector"] = vector
                item["payload"] = payload
                return
        col.append({"id": id, "vector": vector, "payload": payload})

    async def search(
        self,
        collection: str,
        query_vector: list[float],
        top_k: int = 5,
        filter: dict | None = None,
    ) -> list[VectorSearchResult]:
        col = self._collections.get(collection, [])
        scored = [
            (item, self._cosine(query_vector, item["vector"]))
            for item in col
        ]
        scored.sort(key=lambda x: x[1], reverse=True)
        return [
            VectorSearchResult(id=item["id"], score=score, payload=item["payload"])
            for item, score in scored[:top_k]
        ]

    async def delete(self, collection: str, id: str) -> None:
        col = self._collections.get(collection, [])
        self._collections[collection] = [i for i in col if i["id"] != id]

    async def create_collection(
        self, collection: str, vector_size: int, distance: str = "Cosine"
    ) -> None:
        self._collections.setdefault(collection, [])


# ── Qdrant provider ───────────────────────────────────────────────────────────

class QdrantProvider:
    """
    Qdrant vector database provider.
    Requires: QDRANT_URL (default: http://localhost:6333)
    Optional: QDRANT_API_KEY
    """

    def __init__(self) -> None:
        try:
            from qdrant_client import AsyncQdrantClient
            from qdrant_client.models import Distance, VectorParams
        except ImportError as e:
            raise ImportError("Install qdrant-client: pip install qdrant-client") from e

        self._url = os.getenv("QDRANT_URL", "http://localhost:6333")
        self._api_key = os.getenv("QDRANT_API_KEY")
        self._client = AsyncQdrantClient(url=self._url, api_key=self._api_key)

    async def upsert(
        self, collection: str, id: str, vector: list[float], payload: dict
    ) -> None:
        from qdrant_client.models import PointStruct
        await self._client.upsert(
            collection_name=collection,
            points=[PointStruct(id=id, vector=vector, payload=payload)],
        )

    async def search(
        self,
        collection: str,
        query_vector: list[float],
        top_k: int = 5,
        filter: dict | None = None,
    ) -> list[VectorSearchResult]:
        from qdrant_client.models import Filter

        qdrant_filter = None
        if filter:
            # Simple equality filter support
            from qdrant_client.models import FieldCondition, MatchValue, Filter, Must
            conditions = [
                FieldCondition(key=k, match=MatchValue(value=v))
                for k, v in filter.items()
            ]
            qdrant_filter = Filter(must=conditions)

        results = await self._client.search(
            collection_name=collection,
            query_vector=query_vector,
            limit=top_k,
            query_filter=qdrant_filter,
            with_payload=True,
        )
        return [
            VectorSearchResult(
                id=str(r.id),
                score=r.score,
                payload=r.payload or {},
            )
            for r in results
        ]

    async def delete(self, collection: str, id: str) -> None:
        from qdrant_client.models import PointIdsList
        await self._client.delete(
            collection_name=collection,
            points_selector=PointIdsList(points=[id]),
        )

    async def create_collection(
        self, collection: str, vector_size: int, distance: str = "Cosine"
    ) -> None:
        from qdrant_client.models import Distance, VectorParams
        dist_map = {"Cosine": Distance.COSINE, "Dot": Distance.DOT, "Euclid": Distance.EUCLID}
        await self._client.recreate_collection(
            collection_name=collection,
            vectors_config=VectorParams(
                size=vector_size,
                distance=dist_map.get(distance, Distance.COSINE),
            ),
        )


# ── Provider registry ─────────────────────────────────────────────────────────

_provider = None


def _build_provider():
    name = os.getenv("PLATFORM_VECTOR_BACKEND", "memory").lower()
    if name in ("memory", "mock"):
        return MemoryVectorProvider()
    if name == "qdrant":
        return QdrantProvider()
    raise EnvironmentError(f"Unknown PLATFORM_VECTOR_BACKEND={name!r}. Valid: memory, qdrant")


def get_provider():
    global _provider
    if _provider is None:
        _provider = _build_provider()
    return _provider


def _reset_provider() -> None:
    global _provider
    _provider = None


# ── Public API ────────────────────────────────────────────────────────────────

async def vector_upsert(
    collection: str,
    id: str,
    vector: list[float],
    payload: dict | None = None,
) -> None:
    """Store or update a vector with its payload."""
    await get_provider().upsert(collection, id, vector, payload or {})


async def vector_search(
    collection: str,
    query_vector: list[float],
    top_k: int = 5,
    filter: dict | None = None,
) -> list[VectorSearchResult]:
    """
    Search for nearest vectors.

    Args:
        collection:   Collection/index name.
        query_vector: Query embedding vector.
        top_k:        Number of results to return.
        filter:       Optional metadata filter dict, e.g. {"category": "docs"}.

    Usage:
        results = await vector_search("knowledge_base", query_embedding, top_k=5)
        for r in results:
            print(r.score, r.payload["text"])
    """
    return await get_provider().search(collection, query_vector, top_k, filter)


async def vector_delete(collection: str, id: str) -> None:
    """Delete a vector by ID."""
    await get_provider().delete(collection, id)


async def create_collection(
    collection: str, vector_size: int, distance: str = "Cosine"
) -> None:
    """Create a new vector collection."""
    await get_provider().create_collection(collection, vector_size, distance)


# ── MCP handlers ──────────────────────────────────────────────────────────────

async def _mcp_query_vector(args: dict) -> dict:
    # Import embed at runtime — tier3 cannot import tier4 at module load time
    from platform_sdk.tier4_advanced.inference import embed as _embed  # noqa: PLC0415
    query_text = args["query"]
    collection = args.get("collection", "default")
    top_k = args.get("top_k", 5)
    vectors = await _embed([query_text])
    results = await vector_search(
        collection=collection,
        query_vector=vectors[0],
        top_k=top_k,
    )
    return {
        "results": [
            {"id": r.id, "score": r.score, "payload": r.payload}
            for r in results
        ],
    }


async def _mcp_upsert_vector(args: dict) -> dict:
    # Import embed at runtime — tier3 cannot import tier4 at module load time
    from platform_sdk.tier4_advanced.inference import embed as _embed  # noqa: PLC0415
    text = args["text"]
    vectors = await _embed([text])
    await vector_upsert(
        collection=args.get("collection", "default"),
        id=args["id"],
        vector=vectors[0],
        payload={"text": text, **(args.get("metadata") or {})},
    )
    return {"upserted": True, "id": args["id"]}


__sdk_export__ = {
    "surface": "agent",
    "exports": ["vector_search", "vector_upsert", "vector_delete"],
    "mcp_tools": [
        {
            "name": "query_vector",
            "description": "Perform a similarity search in the platform vector store. Query text is automatically embedded.",
            "schema": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query text (automatically embedded)",
                    },
                    "collection": {"type": "string", "default": "default"},
                    "top_k": {"type": "integer", "default": 5},
                },
                "required": ["query"],
            },
            "handler": "_mcp_query_vector",
        },
        {
            "name": "upsert_vector",
            "description": "Add or update a document in the platform vector store. Text is automatically embedded.",
            "schema": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "text": {"type": "string"},
                    "collection": {"type": "string", "default": "default"},
                    "metadata": {"type": "object"},
                },
                "required": ["id", "text"],
            },
            "handler": "_mcp_upsert_vector",
        },
    ],
    "description": "Vector store abstraction for embeddings and RAG (Qdrant or in-memory)",
    "tier": "tier3_platform",
    "module": "vector",
}
