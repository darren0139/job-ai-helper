"""Optional ChromaDB retrieval for Phase 6D capability records.

RAG retrieves candidate capability IDs. It never decides direct/transferable/
weak/none; the deterministic taxonomy matcher still owns that decision.
"""

from __future__ import annotations

import os
import hashlib
import json
import time
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

    started_at = time.perf_counter()
    response = embedding(
        model=EMBEDDING_MODEL,
        input=texts,
    )
    elapsed_seconds = time.perf_counter() - started_at

    try:
        from llm import record_external_usage

        response_model = (
            response.get("model")
            if isinstance(response, dict)
            else getattr(response, "model", None)
        )
        response_usage = (
            response.get("usage")
            if isinstance(response, dict)
            else getattr(response, "usage", None)
        )
        record_external_usage(
            route="analysis",
            requested_model=EMBEDDING_MODEL,
            response_model=response_model,
            usage=response_usage,
            elapsed_seconds=elapsed_seconds,
            operation="taxonomy_embedding",
        )
    except Exception:
        # Retrieval diagnostics must not break analysis or indexing.
        pass

    data = (
        response.get("data", [])
        if isinstance(response, dict)
        else getattr(response, "data", [])
    )
    return [
        item["embedding"] if isinstance(item, dict) else item.embedding
        for item in data
    ]


def _index_identity(taxonomy):
    # Includes predicates, priority and model, not just the rendered documents.
    material = {"version": taxonomy.version, "capabilities": taxonomy.capabilities,
                "embedding_model": EMBEDDING_MODEL}
    return hashlib.sha256(json.dumps(material, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _collection(taxonomy, *, create=False):
    import chromadb
    identity = _index_identity(taxonomy)
    if create:
        CHROMA_PATH.mkdir(parents=True, exist_ok=True)
    elif not CHROMA_PATH.is_dir():
        raise ValueError("Taxonomy index missing; administrative rebuild required")
    client = chromadb.PersistentClient(path=str(CHROMA_PATH))
    name = f"{COLLECTION_NAME}_{identity[:24]}"
    if create:
        return client.get_or_create_collection(name=name, metadata={"index_identity": identity, "taxonomy_version": taxonomy.version})
    return client.get_collection(name=name)


def rebuild_taxonomy_index(taxonomy=None, *, administrative=False):
    if not administrative:
        raise PermissionError("Taxonomy indexing requires explicit administrative mode")
    taxonomy = taxonomy or get_default_taxonomy()
    rows = taxonomy_documents(taxonomy)
    documents = [row["document"] for row in rows]
    embeddings = _embed_texts(documents)
    if len(embeddings) != len(rows):
        raise RuntimeError("Embedding count mismatch")
    collection = _collection(taxonomy, create=True)
    collection.upsert(ids=[row["id"] for row in rows], documents=documents,
                      embeddings=embeddings, metadatas=[row["metadata"] for row in rows])
    return len(rows)


def retrieve_taxonomy_candidates(
    query: str,
    *,
    top_k: int = 5,
    use_embeddings: bool = True,
    administrative: bool = False,
) -> list[dict[str, Any]]:
    cleaned = query.strip()
    if not cleaned:
        raise ValueError("Capability query cannot be empty.")

    if not use_embeddings:
        return lexical_retrieve(cleaned, top_k=top_k)

    if not administrative:
        raise PermissionError("Vector taxonomy retrieval requires explicit administrative mode")
    taxonomy = get_default_taxonomy()
    collection = _collection(taxonomy, create=False)
    expected = _index_identity(taxonomy)
    if (collection.metadata or {}).get("index_identity") != expected or not int(collection.count()):
        raise ValueError("Taxonomy index is stale/missing; rebuild explicitly in administrative mode")

    vector = _embed_texts([cleaned])[0]
    result = collection.query(
        query_embeddings=[vector],
        n_results=min(top_k, int(collection.count())),
        include=["documents", "metadatas", "distances"],
    )
    docs = result.get("documents", [[]])[0]
    metas = result.get("metadatas", [[]])[0]
    distances = result.get("distances", [[]])[0]
    if any((meta or {}).get("taxonomy_version") != taxonomy.version for meta in metas):
        raise ValueError("Stale taxonomy index row")
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
