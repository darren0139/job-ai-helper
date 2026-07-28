"""Optional ChromaDB retrieval for Phase 6D capability records.

RAG retrieves candidate capability IDs. It never decides direct/transferable/
weak/none; the deterministic taxonomy matcher still owns that decision.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from tailoring.capability_taxonomy import (
    CapabilityTaxonomy,
    get_default_taxonomy,
    normalise,
    taxonomy_documents,
)

CHROMA_PATH = Path("data/chroma_capability_taxonomy")
COLLECTION_NAME = "capability_taxonomy_v1"
EMBEDDING_MODEL = os.getenv(
    "CAPABILITY_EMBEDDING_MODEL",
    os.getenv("EMBEDDING_MODEL", "openai/text-embedding-3-small"),
)


def _tokenise(value: str) -> set[str]:
    return {
        token
        for token in normalise(value).split()
        if len(token) >= 2
    }


def lexical_retrieve(
    query: str,
    *,
    taxonomy: CapabilityTaxonomy | None = None,
    top_k: int = 5,
) -> list[dict[str, Any]]:
    """Offline deterministic fallback used by tests and local development."""
    taxonomy = taxonomy or get_default_taxonomy()
    query_tokens = _tokenise(query)
    ranked: list[tuple[float, dict[str, Any]]] = []

    for row in taxonomy_documents(taxonomy):
        doc_tokens = _tokenise(row["document"])
        overlap = len(query_tokens & doc_tokens)
        score = overlap / max(1, len(query_tokens))
        ranked.append((score, row))

    ranked.sort(
        key=lambda pair: (
            pair[0],
            pair[1]["metadata"]["capability_id"],
        ),
        reverse=True,
    )
    return [
        {**row, "score": round(score, 6), "retrieval": "lexical"}
        for score, row in ranked[: max(1, top_k)]
        if score > 0
    ]


def _embed_texts(texts: list[str]) -> list[list[float]]:
    from litellm import embedding

    response = embedding(model=EMBEDDING_MODEL, input=texts)
    data = (
        response.get("data", [])
        if isinstance(response, dict)
        else getattr(response, "data", [])
    )
    return [
        item["embedding"] if isinstance(item, dict) else item.embedding
        for item in data
    ]


def _collection():
    import chromadb

    CHROMA_PATH.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=str(CHROMA_PATH))
    return client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"description": "Phase 6D capability taxonomy"},
    )


def rebuild_taxonomy_index(
    taxonomy: CapabilityTaxonomy | None = None,
) -> int:
    taxonomy = taxonomy or get_default_taxonomy()
    rows = taxonomy_documents(taxonomy)
    collection = _collection()

    try:
        existing = collection.get(include=[])
        ids = existing.get("ids", []) if isinstance(existing, dict) else []
        if ids:
            collection.delete(ids=ids)
    except Exception:
        pass

    documents = [row["document"] for row in rows]
    embeddings = _embed_texts(documents)
    if len(embeddings) != len(rows):
        raise RuntimeError(
            f"Embedding count mismatch: expected {len(rows)}, got {len(embeddings)}"
        )

    collection.upsert(
        ids=[row["id"] for row in rows],
        documents=documents,
        embeddings=embeddings,
        metadatas=[row["metadata"] for row in rows],
    )
    return len(rows)


def retrieve_taxonomy_candidates(
    query: str,
    *,
    top_k: int = 5,
    use_embeddings: bool = True,
) -> list[dict[str, Any]]:
    cleaned = query.strip()
    if not cleaned:
        raise ValueError("Capability query cannot be empty.")

    if not use_embeddings:
        return lexical_retrieve(cleaned, top_k=top_k)

    collection = _collection()
    if int(collection.count()) == 0:
        rebuild_taxonomy_index()

    vector = _embed_texts([cleaned])[0]
    result = collection.query(
        query_embeddings=[vector],
        n_results=min(top_k, int(collection.count())),
        include=["documents", "metadatas", "distances"],
    )
    docs = result.get("documents", [[]])[0]
    metas = result.get("metadatas", [[]])[0]
    distances = result.get("distances", [[]])[0]
    return [
        {
            "id": (meta or {}).get("capability_id", ""),
            "document": doc,
            "metadata": meta or {},
            "distance": distance,
            "retrieval": "embedding",
        }
        for doc, meta, distance in zip(docs, metas, distances)
    ]
