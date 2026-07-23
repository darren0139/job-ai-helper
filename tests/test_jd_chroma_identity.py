from __future__ import annotations

import unittest
from unittest.mock import patch

from rag import jd_chroma_rag as rag


class FakeCollection:
    def __init__(self) -> None:
        self.deleted_where: list[dict] = []
        self.upserts: list[dict] = []

    def delete(self, *, where: dict) -> None:
        self.deleted_where.append(where)

    def upsert(self, **kwargs) -> None:
        self.upserts.append(kwargs)


class JDChromaIdentityTests(unittest.TestCase):
    def test_canonical_chunk_ids_and_metadata_are_stable(self) -> None:
        collection = FakeCollection()
        job = {
            "id": 7,
            "application_id": 1,
            "application_count": 2,
            "title": "Software Engineer",
            "company": "Example",
            "location": "Singapore",
            "source_type": "application_session",
            "source_url": "",
            "raw_text": "Build Python APIs.",
            "jd_profile": {"required_skills": ["Python"]},
            "canonical_jd_id": "jd_abc123",
            "source_version_id": "jdv_version1",
        }

        with (
            patch.object(rag, "get_job_description_by_id", return_value=job),
            patch.object(rag, "get_chroma_collection", return_value=collection),
            patch.object(rag, "embed_texts", side_effect=lambda texts: [[0.1, 0.2] for _ in texts]),
        ):
            chunk_count = rag.index_job_description_to_chroma(7)

        self.assertGreater(chunk_count, 0)
        upsert = collection.upserts[0]
        self.assertTrue(all(item.startswith("jd_abc123:chunk:") for item in upsert["ids"]))
        self.assertTrue(all(meta["canonical_jd_id"] == "jd_abc123" for meta in upsert["metadatas"]))
        self.assertTrue(all(meta["source_version_id"] == "jdv_version1" for meta in upsert["metadatas"]))

    def test_delete_supports_canonical_id_after_database_row_is_gone(self) -> None:
        collection = FakeCollection()
        with patch.object(rag, "get_chroma_collection", return_value=collection):
            rag.delete_job_description_from_chroma(canonical_jd_id="jd_deleted")
        self.assertIn({"canonical_jd_id": "jd_deleted"}, collection.deleted_where)


if __name__ == "__main__":
    unittest.main()
