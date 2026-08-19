from __future__ import annotations

import unittest

from analysis_stability.stable_evidence_scoring import (
    build_deterministic_keyword_match,
    build_stable_analysis,
    canonicalise_requirements,
)
from tailoring.fresh_target_evidence_scoring import (
    FRESH_TARGET_EVIDENCE_POLICY_VERSION,
    build_fresh_target_analysis,
)
from tailoring.phase9c_blueprint_evaluation import _target_analysis


JD_PROFILE = {
    "company": "Garena",
    "job_title": "Associate, Configuration & QA",
    "required_skills": [
        "Passionate about games with basic knowledge of the gaming industry, preferably being familiar with recent shooting games",
    ],
    "responsibilities": [
        "Operate and maintain the daily operations of the gaming product from configuration, quality assurance, live environment handling (including bugs and hacks), and operational evaluation",
        "Coordinate configuration & QA tasks between different offices",
        "Collaborate with both local and global stakeholders in resolving product-related problems",
    ],
    "soft_skills": [
        "Good written and verbal communication skills along with the ability to effectively collaborate with cross-functional teams",
    ],
    "preferred_skills": [
        "Having a track record of working with meticulous works that require high attention to detail would be preferred",
    ],
    "deal_breakers": [
        "Minimum 1 year of experience in quality assurance, live operations, or related fields, preferably within tech or gaming companies",
    ],
    "tools_technologies": [],
}

RAW_JD = "\n".join(
    [
        "Garena Associate, Configuration & QA",
        *JD_PROFILE["responsibilities"],
        *JD_PROFILE["deal_breakers"],
        *JD_PROFILE["required_skills"],
        *JD_PROFILE["soft_skills"],
        *JD_PROFILE["preferred_skills"],
    ]
)

RESUME_PROFILE = {
    "name": "Candidate",
    "summary": "",
    "experience": [
        {
            "title": "Software Engineer Intern",
            "company": "Example",
            "date": "May 2025 - Apr 2026",
            "bullets": [
                "Collaborated on backend API integration and object storage for a data visualisation workflow."
            ],
        },
        {
            "title": "Game Developer Intern",
            "company": "Example",
            "date": "Jul 2018 - Jan 2019",
            "bullets": [
                "Collaborated with a six-person intern team in a Scrum environment to integrate features into a completed simulation."
            ],
        },
    ],
    "projects": [
        {
            "title": "Job AI Helper",
            "date": "May 2026 - Aug 2026",
            "bullets": [
                "Added automated unit tests and GitHub Actions CI across Ubuntu and Windows, running dependency checks, compilation, the full test suite, and a Streamlit startup health check.",
                "Created a multi-step LLM pipeline for resume profile extraction, JD extraction, keyword matching, bullet review, structure audit, jargon audit, degree fit, and summary generation.",
            ],
        },
        {
            "title": "QueryAI",
            "date": "Mar 2025 - Apr 2025",
            "bullets": [
                "Implemented backend data access through PostgREST and applied Row-Level Security policies to secure database operations.",
                "Set up the React and Supabase project environment and connected the frontend to the PostgreSQL-backed service.",
            ],
        },
        {
            "title": "The Great Migration",
            "date": "Sep 2023 - Apr 2024",
            "bullets": [
                "Built a C++ asset manager for a custom game engine, centralising asset loading and improving pipeline consistency."
            ],
        },
        {
            "title": "CyberSphere",
            "date": "Jan 2018 - Feb 2018",
            "bullets": [
                "Scripted Unity gameplay features for a mobile game published on Google Play."
            ],
        },
    ],
    "education": [
        {
            "degree": "Bachelor of Science with Honours in Computer Science in Interactive Media and Game Development",
            "school": "Example University",
            "graduation_date": "Aug 2022 - Apr 2026",
        }
    ],
    "skills": {
        "Programming": ["Python", "C++", "C#"],
        "Game & Engine": ["Unity Engine", "FMOD"],
        "Tools": ["GitHub", "GitHub Actions"],
    },
}


def _resume_text() -> str:
    lines: list[str] = []
    for project in RESUME_PROFILE["projects"]:
        lines.append(project["title"])
        lines.extend(project["bullets"])
    for experience in RESUME_PROFILE["experience"]:
        lines.append(experience["title"])
        lines.extend(experience["bullets"])
    for education in RESUME_PROFILE["education"]:
        lines.append(education["degree"])
    return "\n".join(lines)


def _analyses():
    canonical = canonicalise_requirements(jd_profile=JD_PROFILE, raw_jd_text=RAW_JD)
    keyword_match = build_deterministic_keyword_match(
        requirements=canonical["requirements"],
        acronym_map=canonical["acronym_map"],
        resume_profile=RESUME_PROFILE,
        raw_resume_text=_resume_text(),
    )
    base = build_stable_analysis(
        jd_profile=JD_PROFILE,
        keyword_match=keyword_match,
        raw_jd_text=RAW_JD,
        raw_resume_text=_resume_text(),
        resume_profile=RESUME_PROFILE,
        retrieval_mode_override="lexical",
    )
    fresh = build_fresh_target_analysis(
        jd_profile=JD_PROFILE,
        keyword_match=keyword_match,
        raw_jd_text=RAW_JD,
        raw_resume_text=_resume_text(),
        resume_profile=RESUME_PROFILE,
        retrieval_mode_override="lexical",
    )
    return canonical, base, fresh


def _rows_by_capability(analysis, capability_id):
    rows = [
        row
        for row in analysis["canonical_requirements"]
        if row.get("capability_id") == capability_id
    ]
    if not rows:
        raise AssertionError(f"Missing capability row: {capability_id}")
    return rows


class FreshScorerEvidenceRediscoveryTests(unittest.TestCase):
    def test_known_visible_evidence_is_rediscovered_without_history(self):
        _, base, fresh = _analyses()
        self.assertGreater(
            fresh["deterministic_alignment_score"],
            base["deterministic_alignment_score"],
        )
        self.assertEqual(
            fresh["fresh_target_evidence_policy_version"],
            FRESH_TARGET_EVIDENCE_POLICY_VERSION,
        )
        report = fresh["fresh_evidence_rediscovery"]
        self.assertFalse(report["historical_phase8_answers_used"])
        self.assertFalse(report["generation_mappings_used"])
        self.assertEqual(report["model_call_count"], 0)
        self.assertEqual(report["embedding_call_count"], 0)
        self.assertEqual(report["chroma_call_count"], 0)

        self.assertTrue(
            any(
                row["match_label"] == "direct"
                for row in _rows_by_capability(fresh, "domain.game_knowledge")
            )
        )
        self.assertTrue(
            any(
                row["match_label"] == "weak"
                for row in _rows_by_capability(fresh, "quality.qa_testing")
            )
        )
        self.assertTrue(
            any(
                row["match_label"] == "weak"
                for row in _rows_by_capability(fresh, "operations.configuration")
            )
        )
        self.assertTrue(
            any(
                row["match_label"] == "weak"
                for row in _rows_by_capability(fresh, "quality.attention_detail")
            )
        )

    def test_truth_ceiling_guards_remain_fail_closed(self):
        _, _, fresh = _analyses()
        self.assertTrue(
            all(
                row["match_label"] == "none"
                for row in _rows_by_capability(fresh, "experience.duration")
            )
        )
        self.assertTrue(
            all(
                row["match_label"] == "none"
                for row in _rows_by_capability(fresh, "motivation.subjective")
            )
        )
        self.assertTrue(
            all(
                row["match_label"] == "none"
                for row in _rows_by_capability(fresh, "operations.daily")
            )
        )

    def test_phase9c_target_uses_same_fresh_policy(self):
        canonical, _, expected = _analyses()
        candidate = {
            "resume_profile_snapshot": RESUME_PROFILE,
            "resume_text_snapshot": _resume_text(),
        }
        jd = {"jd_profile": JD_PROFILE, "raw_text": RAW_JD}
        actual = _target_analysis(candidate, jd, canonical)
        self.assertEqual(
            actual["fresh_target_evidence_policy_version"],
            FRESH_TARGET_EVIDENCE_POLICY_VERSION,
        )
        self.assertEqual(
            actual["deterministic_alignment_score"],
            expected["deterministic_alignment_score"],
        )


if __name__ == "__main__":
    unittest.main()
