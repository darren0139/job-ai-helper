from copy import deepcopy
import unittest

from tailoring import application_development_evidence_v312b219c as policy
from tailoring.stable_tailoring_ranking import (
    build_bullet_evidence_priorities,
    rank_projects_deterministically,
)

GENERAL = "Develop software applications"
FEATURE = "Implement application features"
SPECIFIED = "Develop and enhance software applications to meet functional and technical specifications"
MAINTENANCE = "Continually improve and maintain software applications"

BUILT = "Built an AI-assisted Streamlit application for résumé tailoring."
SESSION = "Implemented SQLite-backed application sessions with persistent chat history."
IMPROVED = "Enhanced the mobile application with offline search."
MAINTAINED = "Regularly improved and maintained the desktop application across successive releases."
SPEC = "Developed and enhanced the web application to meet functional and technical specifications."


class ApplicationDevelopmentTests(unittest.TestCase):
    def test_owned_application_work_and_qualified_requirements(self):
        for req, evidence, expected in (
            (GENERAL, BUILT, "direct"), (GENERAL, "Built a mobile application in Kotlin.", "direct"),
            ("Software development", "Built a desktop application using Electron.", "direct"),
            (GENERAL, "Built a custom game engine using C++.", "direct"),
            (GENERAL, IMPROVED, "direct"), (FEATURE, SESSION, "direct"),
            (GENERAL, "Built gameplay and UI features in a small team, contributing to a completed mobile game released on Google Play.", "direct"),
            (GENERAL, "Implemented image attachment support using Coil and contributed to user-facing mobile app workflows.", "direct"),
            (GENERAL, "Built a full-stack IT service request tracker with React, FastAPI, and PostgreSQL.", "direct"),
            (FEATURE, BUILT, None), (MAINTENANCE, BUILT, None),
            (MAINTENANCE, MAINTAINED, "direct"), (SPECIFIED, BUILT, None),
            (SPECIFIED, "Developed and enhanced the web application to meet technical specifications.", None),
            (SPECIFIED, SPEC, "direct"),
        ):
            with self.subTest(req=req, evidence=evidence):
                spec = policy.requirement({"text": req})
                self.assertIsNotNone(spec)
                self.assertEqual(policy.evaluate(spec, evidence), expected)

    def test_excludes_unowned_unperformed_and_adjacent_work(self):
        spec = policy.requirement({"text": GENERAL})
        for evidence in (
            "Would have built a web application.", "The vendor built a web application.",
            "Created a presentation about a mobile app.", "Did not build an application.",
            "Architected a web application on paper.",
            "Deployed an application through a managed service.",
            "Built a CI pipeline for the application.", "Built automated frontend tests for the web application.",
            "Built a website using third-party software; another team implemented the application.",
            "Integrated an external payment API with the application.",
            "Built a mechanical system using a mobile app.",
        ):
            with self.subTest(evidence=evidence):
                self.assertIsNone(policy.evaluate(spec, evidence))

    def test_specialized_and_non_eligible_requirements_keep_existing_authority(self):
        for req in ("Develop RESTful APIs", "Design and implement databases",
                    "Experience in frontend and backend web application development"):
            self.assertIsNone(policy.requirement({"text": req}))
        self.assertIsNone(policy.requirement({"text": GENERAL, "score_eligible": False}))

    def test_native_requires_a_visible_single_record(self):
        row = {"requirement_id": "dev", "text": SPECIFIED, "importance": "core",
               "group_weight_fraction": 0.5, "match_label": "none"}
        rows = [deepcopy(row)]
        evidence = [{"evidence_id": "hidden", "source": "resume_profile.projects[0].bullets[0]",
                     "text": SPEC, "section": "projects"}]
        policy.apply_policy(rows, evidence, BUILT + "\nImproved the application against specifications.")
        self.assertEqual(rows[0]["match_label"], "none")
        policy.apply_policy(rows, evidence, SPEC)
        self.assertEqual(rows[0]["match_label"], "direct")
        self.assertEqual(rows[0]["evidence"][0]["text"], SPEC)
        for key in ("requirement_id", "group_weight_fraction", "importance"):
            self.assertEqual(rows[0][key], row[key])

    def test_fresh_project_link_reaches_exact_bullet_priorities(self):
        candidate = {"title": "Owned App", "resume_evidence": {"bullets": [BUILT, "Deployed the application."]}}
        ranked, _ = rank_projects_deterministically(
            ranked_rows=[{"title": candidate["title"]}],
            project_candidates=[candidate],
            stable_analysis={"canonical_requirements": [
                {"requirement_id": "dev", "text": GENERAL, "importance": "core"},
                {"requirement_id": "maintenance", "text": MAINTENANCE, "importance": "core"},
            ]},
        )
        matches = ranked[0]["requirement_matches"]
        self.assertEqual([match["requirement_id"] for match in matches], ["dev"])
        self.assertEqual(matches[0]["application_development_version"], policy.VERSION)
        priorities = build_bullet_evidence_priorities(
            bullets=candidate["resume_evidence"]["bullets"], ranking_row=ranked[0])
        self.assertEqual([row["supported_requirement_ids"] for row in priorities], [["dev"], []])
        self.assertTrue(priorities[0]["protect_during_fitting"])
