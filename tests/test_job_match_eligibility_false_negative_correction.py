"""Focused offline coverage for Job Match eligibility and false negatives."""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import unittest

from analysis_stability.stable_evidence_scoring import (
    CREDENTIAL_EVIDENCE_POLICY_VERSION,
    IMPORTANCE_WEIGHTS,
    MATCH_VALUES,
    _weighted_coverage,
    build_deterministic_keyword_match,
    build_stable_analysis,
    canonicalise_requirements,
)
from job_discovery.matching import build_profile_evidence_context
from taxonomy_discovery.regression_corpus import (
    CORPUS_VERSION,
    replay_current_corpus,
)
from tests.tqd3_publication_fixture_support import PublicationFixture


def _stable(requirement: str, *, resume_profile=None, raw_resume_text=""):
    profile = resume_profile or {}
    canonical = canonicalise_requirements(
        {"required_skills": [requirement]},
        "Requirements\n" + requirement,
    )
    keyword = build_deterministic_keyword_match(
        requirements=canonical["requirements"],
        acronym_map=canonical["acronym_map"],
        resume_profile=profile,
        raw_resume_text=raw_resume_text,
    )
    return build_stable_analysis(
        jd_profile={"required_skills": [requirement]},
        keyword_match=keyword,
        raw_jd_text="Requirements\n" + requirement,
        resume_profile=profile,
        raw_resume_text=raw_resume_text,
        retrieval_mode_override="off",
    )


class StageAEligibilityTests(unittest.TestCase):
    def test_administrative_rows_are_filtered_but_similar_real_requirements_survive(self):
        excluded = (
            "Only shortlisted candidates will be notified",
            "Candidates should be comfortable completing an online technical coding assessment as part of the interview process",
            "160 Robinson Road, #13-07/08/09 SBF Center, Singapore 068914",
            "By submitting your application for this position, you consent to the collection, use, and disclosure of your personal data by the recruiter",
            "EA Licence No.: 16S8067",
        )
        for text in excluded:
            with self.subTest(text=text):
                canonical = canonicalise_requirements(
                    {"required_skills": [text]}, "Requirements\n" + text
                )
                self.assertEqual(canonical["requirements"], [])
                self.assertEqual(len(canonical["filtered_non_requirement_rows"]), 1)
                self.assertFalse(
                    canonical["filtered_non_requirement_rows"][0]["score_eligible"]
                )

        genuine = (
            "Implement data governance controls for sensitive personal data",
            "Design coding assessment infrastructure for engineering candidates",
            "Maintain applications during shortlisted release windows",
        )
        for text in genuine:
            with self.subTest(text=text):
                rows = canonicalise_requirements(
                    {"required_skills": [text]}, "Requirements\n" + text
                )["requirements"]
                self.assertEqual(len(rows), 1)
                self.assertTrue(rows[0]["score_eligible"])

    def test_non_requirement_narrative_is_narrow_and_real_responsibilities_remain(self):
        excluded = (
            "This role reports to the programme director and works closely with engineering teams",
            "Throughout the project, you will gain hands-on experience across the AI solution lifecycle",
            "At IMDA, we recognize the vital role that Quality Assurance plays in software quality",
            "You'll be a key member of the analytics team, sitting at the intersection of AI quality assurance and data analytics",
        )
        for text in excluded:
            with self.subTest(text=text):
                result = canonicalise_requirements(
                    {"responsibilities": [text]}, "Responsibilities\n" + text
                )
                self.assertEqual(result["requirements"], [])

        genuine = (
            "Contribute to strengthen DevOps methodologies and best practices within the organization",
            "Help the organisation maintain a well-documented defensible security posture",
            "Ensure resilience of our mission-critical applications",
        )
        for text in genuine:
            with self.subTest(text=text):
                rows = canonicalise_requirements(
                    {"responsibilities": [text]}, "Responsibilities\n" + text
                )["requirements"]
                self.assertTrue(rows)
                self.assertTrue(all(row["score_eligible"] for row in rows))

    def test_explicit_certification_requires_structured_certification_evidence(self):
        requirement = "Certification in ITIL foundation"
        project = {
            "projects": [{
                "title": "IT operations project", "company": "", "date": "",
                "bullets": ["Applied ITIL foundation practices"],
            }],
            "education": [], "certifications": [], "experience": [], "skills": {},
        }
        rejected = _stable(requirement, resume_profile=project)
        row = rejected["canonical_requirements"][0]
        self.assertEqual(row["credential_policy"], "explicit_certification")
        self.assertEqual(row["match_label"], "none")
        self.assertEqual(row["evidence"], [])

        context = build_profile_evidence_context([{
            "id": 7, "category": "Certification", "title": "ITIL Foundation",
            "subtitle": "PeopleCert", "description": "", "period": "2025",
            "skills": [], "tools": [],
        }])
        matched = _stable(
            requirement,
            resume_profile=context["resume_profile"],
            raw_resume_text=context["raw_resume_text"],
        )
        row = matched["canonical_requirements"][0]
        self.assertEqual(row["match_label"], "direct")
        self.assertEqual(row["structured_match_kind"], "explicit_certification")
        self.assertEqual(row["evidence"][0]["section"], "certification")
        self.assertIn("resume_profile.certifications[", row["evidence"][0]["source"])
        self.assertEqual(
            matched["credential_evidence_policy_version"],
            CREDENTIAL_EVIDENCE_POLICY_VERSION,
        )

    def test_explicit_degree_accepts_only_structured_education(self):
        requirement = "Bachelor's degree in Computer Science"
        unrelated_work = {
            "projects": [{
                "title": "Computer Science learning portal", "company": "", "date": "",
                "bullets": ["Built a bachelor's programme portal"],
            }],
            "education": [], "certifications": [], "experience": [], "skills": {},
        }
        rejected = _stable(requirement, resume_profile=unrelated_work)
        self.assertEqual(rejected["canonical_requirements"][0]["match_label"], "none")

        education = {
            "education": [{
                "degree": "Bachelor of Science in Computer Science",
                "school": "Example University", "graduation_date": "2024",
                "courses": [],
            }],
            "certifications": [], "projects": [], "experience": [], "skills": {},
        }
        matched = _stable(requirement, resume_profile=education)
        row = matched["canonical_requirements"][0]
        self.assertEqual(row["credential_policy"], "explicit_education")
        self.assertEqual(row["match_label"], "direct")
        self.assertEqual(row["structured_match_kind"], "education_qualification")
        self.assertEqual(row["evidence"][0]["section"], "education")

    def test_generic_credential_headings_are_excluded_not_matched(self):
        for text in (
            "Skills & Certifications",
            "Certifications in or from the following would be preferred",
            "Preferred Certification/Skills",
        ):
            with self.subTest(text=text):
                canonical = canonicalise_requirements(
                    {"required_skills": [text]}, "Requirements\n" + text
                )
                self.assertEqual(canonical["requirements"], [])
                filtered = canonical["filtered_non_requirement_rows"][0]
                self.assertEqual(filtered["eligibility_rule"], "generic_credential_narrative")

    def test_bounded_named_lists_decompose_without_parent_double_score(self):
        cases = {
            "Proficiency in Python and SQL is expected": [
                "Proficiency in Python", "Proficiency in SQL",
            ],
            "(a) C#, JavaScript, HTML, CSS": ["C#", "JavaScript", "HTML", "CSS"],
        }
        for parent, expected in cases.items():
            with self.subTest(parent=parent):
                rows = canonicalise_requirements(
                    {"required_skills": [parent]}, "Requirements\n" + parent
                )["requirements"]
                self.assertEqual([row["atomic_focus"] for row in rows], expected)
                self.assertNotIn(parent, [row["atomic_focus"] for row in rows])
                self.assertEqual(len({row["atomic_group_id"] for row in rows}), 1)
                self.assertAlmostEqual(sum(row["group_weight_fraction"] for row in rows), 1.0)
                self.assertEqual({row["importance"] for row in rows}, {"core"})
                for row in rows:
                    self.assertTrue(row["score_eligible"])
                    self.assertEqual(row["parent_text"], parent)
                    self.assertEqual(row["source_provenance"][0]["parent_text"], parent)
                    self.assertAlmostEqual(row["group_weight_fraction"], 1 / len(expected))
                scored = deepcopy(rows)
                for row in scored:
                    row.update(match_label="direct", match_value=MATCH_VALUES["direct"], evidence_strength=5)
                # The raw Requirements section uses core importance unless
                # explicit hard-requirement wording makes it required. Match
                # the production required/core scoring bucket without changing
                # that policy or the named-list allocation contract.
                accepted = {"deal_breaker", "required", "core"}
                score, numerator, denominator = _weighted_coverage(scored, accepted)
                self.assertEqual(score, 100.0)
                self.assertEqual(numerator, denominator)
                self.assertEqual(denominator, IMPORTANCE_WEIGHTS["core"])
                self.assertLessEqual(numerator, IMPORTANCE_WEIGHTS["core"])
                # Credit for one child must consume only its bounded share.
                for row in scored[1:]:
                    row.update(match_label="none", match_value=MATCH_VALUES["none"])
                partial, contribution, allocation = _weighted_coverage(scored, accepted)
                self.assertEqual(allocation, IMPORTANCE_WEIGHTS["core"])
                self.assertAlmostEqual(contribution, allocation / len(expected))
                self.assertAlmostEqual(partial, 100 / len(expected))

    def test_open_ended_compounds_remain_unsplit(self):
        cases = (
            "Advanced proficiency in at least one analytical tool such as Python, SQL, Power BI, Tableau, or equivalent tools",
            "Experience with cloud data platforms such as AWS Glue, Azure Data Factory, Google Dataflow, or Databricks",
            "Knowledge of relational and non-relational databases such as SQL Server and MongoDB",
        )
        for text in cases:
            with self.subTest(text=text):
                rows = canonicalise_requirements(
                    {"required_skills": [text]}, "Requirements\n" + text
                )["requirements"]
                self.assertEqual(len(rows), 1)
                self.assertEqual(rows[0]["atomic_focus"], text)

    def test_stage_a_is_read_only_for_production_knowledge(self):
        with PublicationFixture() as fixture:
            _stable("Certification in ITIL foundation", resume_profile={})
        fixture.network_guard.assert_not_called()
        fixture.model_guard.assert_not_called()

    def test_current_corpus_replay_is_explicit_offline_and_read_only(self):
        text = "Certification in ITIL foundation"
        context = build_profile_evidence_context([{
            "id": 7, "category": "Certification", "title": "ITIL Foundation",
            "subtitle": "PeopleCert", "description": "", "period": "2025",
            "skills": [], "tools": [],
        }])
        corpus = {
            "corpus_version": CORPUS_VERSION,
            "jobs": [{
                "job_id": 1,
                "snapshot_id": 2,
                "requirements": [{"requirement_id": "saved", "requirement_text": text}],
                "baseline_stable_analysis": {"canonical_requirements": []},
                "frozen_inputs": {
                    "raw_jd_text": "Requirements\n" + text,
                    "jd_profile": {"required_skills": [text]},
                    "context": context,
                },
            }],
        }
        original = deepcopy(corpus)
        with PublicationFixture() as fixture:
            replayed = replay_current_corpus(corpus)
        self.assertEqual(corpus, original)
        self.assertTrue(replayed["current_replay"]["explicit"])
        self.assertEqual(replayed["current_replay"]["jobs_replayed"], 1)
        self.assertEqual(replayed["current_replay"]["network_calls"], 0)
        self.assertEqual(replayed["current_replay"]["production_mutations"], 0)
        self.assertEqual(replayed["jobs"][0]["saved_requirements"][0]["requirement_id"], "saved")
        self.assertEqual(replayed["jobs"][0]["requirements"][0]["match_label"], "direct")
        fixture.network_guard.assert_not_called()
        fixture.model_guard.assert_not_called()

    def test_streamlit_audit_requests_current_replay_explicitly(self):
        source = (
            Path(__file__).resolve().parents[1]
            / "taxonomy_discovery"
            / "bulk_candidate_operations_ui.py"
        ).read_text(encoding="utf-8")
        self.assertIn("audit_corpus_resolution(replay_current=True)", source)
        self.assertIn("all current scoring units score eligible", source)


class StageBMatcherTests(unittest.TestCase):
    requirement = (
        "Work closely with DSP, FPGA, RF, and System Engineering teams to "
        "support end to end software integration"
    )

    def _profile(self, bullet):
        return {
            "projects": [{"title": "Engine", "bullets": [bullet]}],
            "experience": [], "education": [], "certifications": [], "skills": {},
        }

    def test_grounded_system_integration_false_negative_is_transferable(self):
        bullet = (
            "Collaborated with a custom-engine team to integrate systems across "
            "asset loading, audio, and gameplay workflows."
        )
        row = _stable(self.requirement, resume_profile=self._profile(bullet))[
            "canonical_requirements"
        ][0]
        self.assertEqual(row["match_label"], "transferable")
        self.assertEqual(row["match_value"], MATCH_VALUES["transferable"])
        self.assertEqual(
            row["structured_match_kind"],
            "collaborative_system_integration_transfer",
        )
        self.assertEqual(row["evidence"][0]["section"], "projects")
        self.assertEqual(
            row["evidence"][0]["source"],
            "resume_profile.projects[0].bullets[0]",
        )

    def test_system_integration_transfer_requires_both_behaviors(self):
        controls = (
            "Integrated FMOD audio systems into gameplay features.",
            "Collaborated with a custom-engine team on gameplay features.",
        )
        for bullet in controls:
            with self.subTest(bullet=bullet):
                row = _stable(
                    self.requirement,
                    resume_profile=self._profile(bullet),
                )["canonical_requirements"][0]
                self.assertEqual(row["match_label"], "none")
                self.assertEqual(row["evidence"], [])

    def test_system_integration_evidence_does_not_prove_other_requirements(self):
        profile = self._profile(
            "Collaborated with a custom-engine team to integrate systems across "
            "asset loading, audio, and gameplay workflows."
        )
        for requirement in (
            "Develop secure scalable authentication and authorised APIs",
            "Experience with Kubernetes in production environments",
        ):
            with self.subTest(requirement=requirement):
                row = _stable(requirement, resume_profile=profile)[
                    "canonical_requirements"
                ][0]
                self.assertEqual(row["match_label"], "none")

        compound = (
            "Excellent analytical, debugging, and communication skills, with "
            "the ability to work across cross-functional teams to solve complex "
            "hardware and software integration challenges"
        )
        row = _stable(compound, resume_profile=profile)["canonical_requirements"][0]
        self.assertEqual(row["match_label"], "weak")
        self.assertNotIn("structured_match_kind", row)

    def test_existing_positive_match_is_not_reclassified(self):
        from tailoring.phase6d6_structured_matching import (
            apply_structured_requirement_matches,
        )
        existing = [{
            "requirement_id": "existing",
            "text": self.requirement,
            "atomic_focus": self.requirement,
            "match_label": "weak",
            "match_value": MATCH_VALUES["weak"],
            "evidence_strength": 2,
            "evidence": [{"text": "Existing bounded evidence"}],
        }]
        rows, warnings = apply_structured_requirement_matches(
            existing,
            resume_profile=self._profile(
                "Collaborated with a custom-engine team to integrate systems "
                "across asset loading, audio, and gameplay workflows."
            ),
        )
        self.assertEqual(rows[0]["match_label"], "weak")
        self.assertEqual(rows[0]["structured_match_status"], "not_applicable")
        self.assertEqual(warnings, [])

    def test_scoring_values_and_weights_are_unchanged(self):
        self.assertEqual(
            MATCH_VALUES,
            {"none": 0.0, "weak": 0.20, "transferable": 0.55, "direct": 1.0},
        )
        rows = [{
            "requirement_id": "required",
            "importance": "required",
            "score_eligible": True,
            "match_value": MATCH_VALUES["transferable"],
        }]
        score, numerator, denominator = _weighted_coverage(rows, {"required"})
        self.assertEqual(score, 55.00000000000001)
        self.assertEqual(numerator, 2.2)
        self.assertEqual(denominator, 4.0)


if __name__ == "__main__":
    unittest.main()
