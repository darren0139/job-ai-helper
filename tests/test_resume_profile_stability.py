from __future__ import annotations

import unittest

from analysis_stability.resume_profile_stability import (
    extract_raw_project_headings,
    stabilise_resume_profile_project_titles,
)


RAW = """
EDUCATION
School

PROJECTS
QueryAI (React, Team of 4) Mar 2025 - Apr 2025
• Built a help desk.
The Great Migration (C++ Custom Engine, Team of 8) Sep 2023 - Apr 2024
• Built an asset manager.

SKILLS
Python
"""


class ResumeProfileStabilityTests(unittest.TestCase):
    def test_extracts_exact_project_headings(self):
        headings = extract_raw_project_headings(RAW)
        self.assertEqual(
            [item["title"] for item in headings],
            [
                "QueryAI (React, Team of 4)",
                "The Great Migration (C++ Custom Engine, Team of 8)",
            ],
        )

    def test_restores_shortened_llm_title(self):
        result = stabilise_resume_profile_project_titles(
            {
                "projects": [
                    {
                        "title": "QueryAI",
                        "date": "Mar 2025 - Apr 2025",
                        "bullets": ["Built a help desk."],
                    }
                ]
            },
            RAW,
        )
        self.assertEqual(
            result["projects"][0]["title"],
            "QueryAI (React, Team of 4)",
        )

    def test_existing_full_title_remains_unchanged(self):
        title = "The Great Migration (C++ Custom Engine, Team of 8)"
        result = stabilise_resume_profile_project_titles(
            {"projects": [{"title": title, "date": "", "bullets": []}]},
            RAW,
        )
        self.assertEqual(result["projects"][0]["title"], title)

    def test_ambiguous_base_title_is_not_rewritten(self):
        raw = """
PROJECTS
Demo (Python) Jan 2025 - Feb 2025
• One.
Demo (C++) Mar 2025 - Apr 2025
• Two.
SKILLS
Python
"""
        result = stabilise_resume_profile_project_titles(
            {"projects": [{"title": "Demo", "date": "", "bullets": []}]},
            raw,
        )
        self.assertEqual(result["projects"][0]["title"], "Demo")


if __name__ == "__main__":
    unittest.main()
