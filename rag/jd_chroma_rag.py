"""
rag/jd_chroma_rag.py — ChromaDB vector RAG over canonical job descriptions.

SQLite owns canonical JD/version/session-link metadata. Chroma stores only the
latest source version of each canonical JD, so duplicate application sessions do
not create duplicate embeddings or inflate market-insight counts.
"""

from __future__ import annotations

import json
import os
import re
from collections import Counter
from pathlib import Path
from typing import Any

import chromadb
from litellm import embedding

from database.jd_library_manager import get_all_job_descriptions, get_job_description_by_id
from llm import ask_text


CHROMA_PATH = Path("data/chroma_jd_library")
COLLECTION_NAME = "job_description_chunks"
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "openai/text-embedding-3-small")


JD_CHROMA_QA_PROMPT = """
Instruction:
Answer the user's question using the retrieved job-description chunks.

Context:
You are an AI career assistant. The user has analyzed multiple job descriptions.
The retrieved context was selected using vector similarity search over those job descriptions.

Constraints:
- Use only the retrieved job-description context and optional resume profile.
- Do not invent job requirements.
- Do not claim a skill is common unless it appears in the retrieved context.
- If the retrieved context is insufficient, say so clearly.
- If a resume profile is provided, compare the user's existing skills against the retrieved job requirements.
- Give honest advice. Do not tell the user to add skills or experience they do not truly have.
- Keep the answer practical for a student or junior applicant.

Output:
Return a plain-text answer with clear headings or bullet points.
"""


def _get_chroma_client():
    CHROMA_PATH.mkdir(parents=True, exist_ok=True)
    return chromadb.PersistentClient(path=str(CHROMA_PATH))


def get_chroma_collection():
    """Return the persistent collection used for canonical JD chunks."""
    client = _get_chroma_client()
    return client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"description": "Canonical job description chunks for Job AI Helper"},
    )


def reset_chroma_index() -> None:
    """Delete and recreate the collection, including legacy duplicate records."""
    client = _get_chroma_client()
    try:
        client.delete_collection(COLLECTION_NAME)
    except Exception:
        pass
    client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"description": "Canonical job description chunks for Job AI Helper"},
    )


def split_text(text: str, *, max_chars: int = 1200, overlap: int = 200) -> list[str]:
    """Split text into overlapping character windows."""
    cleaned = re.sub(r"\s+", " ", text).strip()
    if not cleaned:
        return []

    chunks: list[str] = []
    start = 0
    while start < len(cleaned):
        end = min(start + max_chars, len(cleaned))
        chunk = cleaned[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= len(cleaned):
            break
        start = max(0, end - overlap)
    return chunks


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Embed a batch of texts using LiteLLM."""
    if not texts:
        return []

    response = embedding(
        model=os.getenv("EMBEDDING_MODEL", EMBEDDING_MODEL),
        input=texts,
    )
    data = response.get("data", []) if isinstance(response, dict) else getattr(response, "data", [])

    vectors: list[list[float]] = []
    for item in data:
        vectors.append(item["embedding"] if isinstance(item, dict) else item.embedding)
    return vectors


def _delete_where_safely(collection: Any, where: dict[str, Any]) -> None:
    try:
        collection.delete(where=where)
    except Exception:
        pass


def delete_job_description_from_chroma(
    jd_id: int | None = None,
    *,
    canonical_jd_id: str | None = None,
) -> None:
    """
    Delete Chroma chunks for one canonical JD.

    jd_id is retained for backwards compatibility. canonical_jd_id should be
    used when the SQLite row has already been removed.
    """
    collection = get_chroma_collection()
    resolved_canonical_id = str(canonical_jd_id or "").strip()

    if not resolved_canonical_id and jd_id is not None:
        job = get_job_description_by_id(int(jd_id))
        if job:
            resolved_canonical_id = str(job.get("canonical_jd_id") or "").strip()

    if resolved_canonical_id:
        _delete_where_safely(
            collection,
            {"canonical_jd_id": resolved_canonical_id},
        )

    # Remove pre-migration records whose metadata used only job_id.
    if jd_id is not None:
        _delete_where_safely(collection, {"job_id": str(jd_id)})


def build_job_document_text(job: dict[str, Any]) -> str:
    """Combine canonical metadata, structured profile and latest raw text."""
    profile_text = json.dumps(job.get("jd_profile", {}), indent=2, ensure_ascii=False)
    return f"""
CANONICAL JD ID: {job.get("canonical_jd_id", "")}
SOURCE VERSION ID: {job.get("source_version_id", "")}
LINKED APPLICATION COUNT: {job.get("application_count", 0)}
TITLE: {job.get("title", "")}
COMPANY: {job.get("company", "")}
LOCATION: {job.get("location", "")}
SOURCE TYPE: {job.get("source_type", "")}
SOURCE URL: {job.get("source_url", "")}

STRUCTURED JD PROFILE:
{profile_text}

RAW JOB DESCRIPTION:
{job.get("raw_text", "")}
""".strip()


def index_job_description_to_chroma(jd_id: int) -> int:
    """Replace the latest Chroma chunks for one canonical JD."""
    job = get_job_description_by_id(jd_id)
    if not job:
        raise ValueError(f"Job description #{jd_id} was not found.")

    canonical_id = str(job.get("canonical_jd_id") or "").strip()
    source_id = str(job.get("source_version_id") or "").strip()
    if not canonical_id or not source_id:
        raise ValueError(
            f"Job description #{jd_id} has no canonical/source version identity. "
            "Run init_jd_library() before rebuilding Chroma."
        )

    collection = get_chroma_collection()
    delete_job_description_from_chroma(jd_id, canonical_jd_id=canonical_id)

    chunks = split_text(build_job_document_text(job))
    if not chunks:
        return 0

    embeddings = embed_texts(chunks)
    if len(embeddings) != len(chunks):
        raise RuntimeError(
            f"Embedding count mismatch: expected {len(chunks)}, got {len(embeddings)}."
        )

    ids = [f"{canonical_id}:chunk:{index:03d}" for index in range(len(chunks))]
    primary_application_id = job.get("application_id", "")
    metadatas = [
        {
            "job_id": str(jd_id),
            "canonical_jd_id": canonical_id,
            "source_version_id": source_id,
            "application_id": str(primary_application_id or ""),
            "application_count": int(job.get("application_count", 0) or 0),
            "chunk_index": index,
            "title": str(job.get("title", "") or ""),
            "company": str(job.get("company", "") or ""),
            "location": str(job.get("location", "") or ""),
            "source_type": str(job.get("source_type", "") or ""),
            "source_url": str(job.get("source_url", "") or ""),
        }
        for index in range(len(chunks))
    ]

    collection.upsert(
        ids=ids,
        documents=chunks,
        embeddings=embeddings,
        metadatas=metadatas,
    )
    return len(chunks)


def rebuild_chroma_index(limit: int = 200) -> int:
    """Clear legacy records, then rebuild once per canonical JD."""
    jobs = get_all_job_descriptions(limit=limit)
    reset_chroma_index()
    total_chunks = 0
    for job in jobs:
        total_chunks += index_job_description_to_chroma(int(job["id"]))
    return total_chunks


def get_chroma_index_count() -> int:
    return int(get_chroma_collection().count())


def retrieve_relevant_chunks(question: str, *, top_k: int = 6) -> list[dict[str, Any]]:
    cleaned_question = question.strip()
    if not cleaned_question:
        raise ValueError("Please enter a question first.")

    collection = get_chroma_collection()
    record_count = int(collection.count())
    if record_count == 0:
        raise ValueError("The Chroma index is empty. Analyze at least one job first.")

    query_embedding = embed_texts([cleaned_question])[0]
    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=min(top_k, record_count),
        include=["documents", "metadatas", "distances"],
    )

    documents = results.get("documents", [[]])[0]
    metadatas = results.get("metadatas", [[]])[0]
    distances = results.get("distances", [[]])[0]
    return [
        {
            "document": document,
            "metadata": metadata or {},
            "distance": distance,
        }
        for document, metadata, distance in zip(documents, metadatas, distances)
    ]


def format_chunks_for_prompt(chunks: list[dict[str, Any]]) -> str:
    blocks: list[str] = []
    for index, chunk in enumerate(chunks, start=1):
        meta = chunk.get("metadata", {})
        blocks.append(
            f"""
CHUNK {index}
Canonical JD ID: {meta.get("canonical_jd_id", "")}
Source Version ID: {meta.get("source_version_id", "")}
Title: {meta.get("title", "")}
Company: {meta.get("company", "")}
Location: {meta.get("location", "")}
Source Type: {meta.get("source_type", "")}
Source URL: {meta.get("source_url", "")}
Distance: {chunk.get("distance", "")}

TEXT:
{chunk.get("document", "")}
""".strip()
        )
    return "\n\n---\n\n".join(blocks)


def answer_jd_library_question_chroma(
    question: str,
    *,
    resume_profile: dict[str, Any] | None = None,
    top_k: int = 6,
) -> str:
    retrieved_chunks = retrieve_relevant_chunks(question, top_k=top_k)
    context = format_chunks_for_prompt(retrieved_chunks)
    resume_context = (
        json.dumps(resume_profile, indent=2, ensure_ascii=False)
        if resume_profile
        else "No resume profile provided."
    )

    user_prompt = f"""
USER QUESTION:
{question}

OPTIONAL RESUME PROFILE:
{resume_context}

RETRIEVED JOB DESCRIPTION CHUNKS:
{context}
"""
    answer = ask_text(
        JD_CHROMA_QA_PROMPT,
        user_prompt,
        temperature=0.3,
        max_tokens=900,
        route="chat",
    ).strip()
    if not answer:
        raise RuntimeError("The AI returned an empty answer.")
    return answer


# ---------------------------------------------------------------------------
# Market fit scoring across unique canonical job descriptions
# ---------------------------------------------------------------------------

STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from", "has",
    "have", "in", "is", "it", "of", "on", "or", "our", "that", "the", "to",
    "with", "you", "your", "we", "will", "work", "job", "role", "team",
    "candidate", "experience", "skills", "skill", "ability", "knowledge",
}

FIELD_WEIGHTS = {
    "required_skills": 3.0,
    "tools_technologies": 2.5,
    "preferred_skills": 2.0,
    "soft_skills": 1.5,
    "buzzwords": 1.0,
}


def normalize_term(value: str) -> str:
    value = value.strip().lower()
    value = re.sub(r"[^a-z0-9+#.\s/-]", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def tokenize(text: str) -> set[str]:
    words = re.findall(r"[a-zA-Z0-9+#.]+", text.lower())
    return {word for word in words if len(word) >= 2 and word not in STOPWORDS}


def get_common_jd_terms(limit: int = 200, top_n: int = 20) -> dict[str, list[dict[str, Any]]]:
    """Count each term once per unique canonical JD."""
    jobs = get_all_job_descriptions(limit=limit)
    grouped_fields = {
        "required_skills": Counter(),
        "tools_technologies": Counter(),
        "preferred_skills": Counter(),
        "soft_skills": Counter(),
        "buzzwords": Counter(),
    }
    display_names: dict[str, str] = {}

    for job in jobs:
        jd_profile = job.get("jd_profile", {})
        for field in grouped_fields:
            values = jd_profile.get(field, [])
            if not isinstance(values, list):
                continue
            seen_in_this_job: set[str] = set()
            for value in values:
                if not isinstance(value, str) or not value.strip():
                    continue
                normalized = normalize_term(value)
                if not normalized or normalized in seen_in_this_job:
                    continue
                grouped_fields[field][normalized] += 1
                display_names.setdefault(normalized, value.strip())
                seen_in_this_job.add(normalized)

    return {
        field: [
            {
                "term": display_names.get(term, term),
                "count": count,
                "field": field,
            }
            for term, count in counter.most_common(top_n)
        ]
        for field, counter in grouped_fields.items()
    }


def flatten_resume_terms(resume_profile: dict[str, Any]) -> set[str]:
    terms: set[str] = set()
    skills = resume_profile.get("skills", {})
    if isinstance(skills, dict):
        for values in skills.values():
            if not isinstance(values, list):
                continue
            for value in values:
                if isinstance(value, str) and value.strip():
                    terms.add(normalize_term(value))
                    terms.update(tokenize(value))

    for section in ("summary", "projects", "experience", "education"):
        value = resume_profile.get(section)
        if isinstance(value, str):
            terms.update(tokenize(value))
        elif isinstance(value, list):
            for item in value:
                if not isinstance(item, dict):
                    continue
                for field_value in item.values():
                    if isinstance(field_value, str):
                        terms.add(normalize_term(field_value))
                        terms.update(tokenize(field_value))
                    elif isinstance(field_value, list):
                        for entry in field_value:
                            if isinstance(entry, str):
                                terms.add(normalize_term(entry))
                                terms.update(tokenize(entry))
    return terms


def term_matches_resume(term: str, resume_terms: set[str]) -> tuple[bool, str]:
    normalized = normalize_term(term)
    tokens = tokenize(term)
    if normalized in resume_terms:
        return True, "Full term appears in resume profile."
    if tokens:
        overlap = tokens & resume_terms
        required_overlap = max(1, min(len(tokens), 2))
        if len(overlap) >= required_overlap:
            return True, f"Related tokens found: {', '.join(sorted(overlap))}."
    return False, "Not clearly shown in the resume profile."


def compare_resume_to_common_market_skills(
    resume_profile: dict[str, Any],
    *,
    top_n: int = 30,
    min_count: int = 1,
    limit: int = 200,
) -> dict[str, Any]:
    jobs = get_all_job_descriptions(limit=limit)
    common_terms = get_common_jd_terms(limit=limit, top_n=top_n)
    resume_terms = flatten_resume_terms(resume_profile)

    matched: list[dict[str, Any]] = []
    missing: list[dict[str, Any]] = []
    total_weight = 0.0
    matched_weight = 0.0

    for field, rows in common_terms.items():
        field_weight = FIELD_WEIGHTS.get(field, 1.0)
        for row in rows:
            count = int(row.get("count", 0))
            if count < min_count:
                continue
            term = row.get("term", "")
            if not term:
                continue
            weight = count * field_weight
            total_weight += weight
            is_match, reason = term_matches_resume(term, resume_terms)
            output_row = {
                "term": term,
                "field": field,
                "job_count": count,
                "weight": round(weight, 2),
                "match_reason": reason,
            }
            if is_match:
                matched_weight += weight
                matched.append(output_row)
            else:
                missing.append(output_row)

    score = round(100 * matched_weight / total_weight) if total_weight > 0 else 0
    matched.sort(key=lambda item: item["weight"], reverse=True)
    missing.sort(key=lambda item: item["weight"], reverse=True)
    return {
        "market_fit_score": score,
        "jobs_analyzed": len(jobs),
        "total_weight": round(total_weight, 2),
        "matched_weight": round(matched_weight, 2),
        "matched_common_terms": matched,
        "missing_common_terms": missing,
    }
