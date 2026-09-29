from __future__ import annotations

import unittest

from job_discovery.models import NormalizedJob
from job_discovery.text_utils import html_to_text, join_sections, matches_query


class JobDiscoveryModelTests(unittest.TestCase):
    def test_content_hash_is_stable(self) -> None:
        job = NormalizedJob(
            source="x",
            source_job_id="1",
            title="AI Engineer",
            company="Example",
            description="Build AI systems",
            raw_payload={"b": 2, "a": 1},
        )
        self.assertEqual(job.content_hash, job.content_hash)
        self.assertEqual(len(job.content_hash), 64)

    def test_html_to_text_removes_markup_and_script(self) -> None:
        text = html_to_text("<p>Hello <b>world</b></p><script>bad()</script><ul><li>Python</li></ul>")
        self.assertIn("Hello world", text)
        self.assertIn("Python", text)
        self.assertNotIn("bad()", text)

    def test_query_requires_all_tokens(self) -> None:
        self.assertTrue(matches_query("AI Engineer", "Senior AI Engineer", "Python"))
        self.assertFalse(matches_query("AI Engineer", "Data Analyst", "AI reporting"))

    def test_join_sections_is_readable(self) -> None:
        value = join_sections([("Responsibilities", "Build APIs"), ("Requirements", "Python")])
        self.assertIn("Responsibilities\nBuild APIs", value)
        self.assertIn("Requirements\nPython", value)


if __name__ == "__main__":
    unittest.main()
