from __future__ import annotations

import json
import unittest

from tailoring.jd_user_input_overrides import (
    _normalise_saved_raw_jd_text,
    refresh_application_session_analysis_report,
)


class ApplicationSessionRawJdNormalizationTests(unittest.TestCase):
    def test_plain_text_jd_is_unchanged(self) -> None:
        text = "Requirements\\nPython\\nDocker"
        resolved, source, changed = _normalise_saved_raw_jd_text(text)
        self.assertEqual(resolved, text)
        self.assertEqual(source, "stored_raw_jd_text")
        self.assertFalse(changed)

    def test_json_wrapper_prefers_clean_jd_text_over_visible_capture(self) -> None:
        jd_text = (
            "What the role is\\n"
            "Build services.\\n"
            "What we are looking for\\n"
            "Experience with Python and Docker."
        )
        wrapper = json.dumps(
            {
                "ok": True,
                "data": {
                    "capture": {
                        "raw_visible_text": (
                            "A Government Website\\nLog in\\n" + jd_text
                        )
                    },
                    "cleaned": {
                        "cleaning_strategy": "example_sections_v1",
                        "jd_text": jd_text,
                    },
                },
            }
        )

        resolved, source, changed = _normalise_saved_raw_jd_text(wrapper)

        self.assertEqual(resolved, jd_text)
        self.assertEqual(source, "json_field:jd_text")
        self.assertTrue(changed)

    def test_nested_description_object_is_not_stringified_as_jd(self) -> None:
        wrapper = json.dumps(
            {
                "description": {
                    "metadata": {
                        "cleaning_strategy": "example_sections_v1",
                        "jd_character_count": 99,
                    }
                }
            }
        )

        resolved, source, changed = _normalise_saved_raw_jd_text(wrapper)

        self.assertEqual(resolved, wrapper)
        self.assertEqual(source, "stored_raw_jd_text")
        self.assertFalse(changed)

    def test_historical_refresh_scores_jd_body_not_json_metadata(self) -> None:
        jd_text = (
            "Requirements\\n"
            "Experience with Python application development\\n"
        )
        wrapper = json.dumps(
            {
                "ok": True,
                "data": {
                    "cleaned": {
                        "cleaning_strategy": "example_sections_v1",
                        "company": "Example Co",
                        "jd_character_count": len(jd_text),
                        "jd_text": jd_text,
                    },
                    "capture": {
                        "raw_visible_text": (
                            "Example careers website\\n" + jd_text
                        )
                    },
                },
            }
        )
        report = {
            "raw_jd_text": wrapper,
            "jd_profile": {
                "job_title": "Software Engineer",
                "company": "Example Co",
                "location": "",
                "experience_level": "",
                "required_skills": [
                    "Experience with Python application development"
                ],
                "preferred_skills": [],
                "tools_technologies": ["Python"],
                "responsibilities": [],
                "soft_skills": [],
                "buzzwords": [],
                "deal_breakers": [],
            },
            "keyword_match": {
                "present": [],
                "missing": [
                    {"keyword": "Experience with Python application development"}
                ],
            },
            "resume_profile": {
                "skills": {"languages": ["Python"]},
                "education": [],
                "experience": [],
                "projects": [],
            },
            "stable_analysis": {
                "scoring_version": "legacy-scorer",
                "capability_taxonomy_version": "legacy-taxonomy",
            },
            "bullets": {},
            "structure": {},
            "meta": {},
        }

        refreshed = refresh_application_session_analysis_report(report)

        self.assertEqual(refreshed["raw_jd_text"], jd_text)
        currentness = refreshed["meta"]["stable_analysis_currentness"]
        self.assertTrue(currentness["raw_jd_normalized"])
        self.assertEqual(currentness["raw_jd_source"], "json_field:jd_text")

        requirement_text = "\\n".join(
            str(row.get("text") or "")
            for row in refreshed["stable_analysis"]["canonical_requirements"]
        ).lower()
        self.assertNotIn("cleaning_strategy", requirement_text)
        self.assertNotIn("jd_character_count", requirement_text)
        self.assertNotIn("raw_visible_text", requirement_text)


if __name__ == "__main__":
    unittest.main()
