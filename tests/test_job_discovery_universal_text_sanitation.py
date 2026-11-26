from __future__ import annotations

import unittest

from job_discovery.models import NormalizedJob
from job_discovery.pipeline import _sanitize_fetched_job_text


class UniversalJobDiscoveryTextSanitationTests(unittest.TestCase):
    def _job(self, description):
        return NormalizedJob(
            source="fixture",
            source_job_id="fixture:1",
            title="Software Engineer",
            company="Example",
            description=description,
            location="Singapore",
            raw_payload={
                "description": "RAW\u202fPAYLOAD",
                "nested": {"text": "untouched\u200braw"},
            },
        )

    def test_all_sources_receive_final_unicode_whitespace_sanitation(self):
        original = self._job(
            "Job description\r\n\r\n"
            "Partner\u202fwith\u202fstakeholders.\n"
            "Develop\u00a0and\u2007enhance\u200b applications\u2060.\n"
            "Use soft\u00adhyphens safely."
        )

        cleaned = _sanitize_fetched_job_text(original)

        self.assertEqual(
            cleaned.description,
            "\n".join(
                [
                    "Job description",
                    "Partner with stakeholders.",
                    "Develop and enhance applications.",
                    "Use softhyphens safely.",
                ]
            ),
        )
        self.assertEqual(cleaned.raw_payload, original.raw_payload)
        self.assertEqual(
            cleaned.raw_payload["description"],
            "RAW\u202fPAYLOAD",
        )
        self.assertEqual(
            cleaned.raw_payload["nested"]["text"],
            "untouched\u200braw",
        )

    def test_non_text_description_fails_closed_instead_of_becoming_dict_repr(self):
        malformed = self._job(
            {"title": "Job Description", "text": "Build software."}
        )

        with self.assertRaisesRegex(
            ValueError,
            "non-text job description",
        ):
            _sanitize_fetched_job_text(malformed)

    def test_empty_after_sanitation_fails_closed(self):
        malformed = self._job("\u200b\u2060\ufeff")

        with self.assertRaisesRegex(
            ValueError,
            "empty job description",
        ):
            _sanitize_fetched_job_text(malformed)


if __name__ == "__main__":
    unittest.main()
