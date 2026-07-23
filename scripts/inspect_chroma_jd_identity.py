from __future__ import annotations

from collections import Counter, defaultdict

from rag.jd_chroma_rag import get_chroma_collection


def main() -> None:
    collection = get_chroma_collection()
    result = collection.get(include=["metadatas"])
    ids = result.get("ids", []) or []
    metadatas = result.get("metadatas", []) or []

    chunks_per_canonical: Counter[str] = Counter()
    versions_per_canonical: dict[str, set[str]] = defaultdict(set)
    legacy_ids: list[str] = []

    for record_id, metadata in zip(ids, metadatas):
        metadata = metadata or {}
        canonical_id = str(metadata.get("canonical_jd_id") or "").strip()
        source_id = str(metadata.get("source_version_id") or "").strip()
        if not canonical_id:
            legacy_ids.append(str(record_id))
            continue
        chunks_per_canonical[canonical_id] += 1
        if source_id:
            versions_per_canonical[canonical_id].add(source_id)

    print(f"Total Chroma chunks: {len(ids)}")
    print(f"Canonical JDs represented: {len(chunks_per_canonical)}")
    print(f"Legacy chunks missing canonical_jd_id: {len(legacy_ids)}")

    for canonical_id, count in sorted(chunks_per_canonical.items()):
        versions = sorted(versions_per_canonical[canonical_id])
        print(f"  {canonical_id}: chunks={count}, source_versions={versions}")

    if legacy_ids:
        print("\nLegacy records remain; run the canonical Chroma rebuild:")
        print("  python -m scripts.migrate_jd_identity --no-backup --rebuild-chroma")


if __name__ == "__main__":
    main()
