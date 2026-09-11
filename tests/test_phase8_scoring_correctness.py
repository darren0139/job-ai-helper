from __future__ import annotations

import unittest

from analysis_stability.stable_evidence_scoring import (
    SCORING_VERSION,
    canonicalise_requirements,
)
from tailoring.capability_taxonomy import evaluate_evidence, get_default_taxonomy
from tailoring.fresh_target_evidence_scoring import build_fresh_target_analysis
from tailoring.phase8_requirement_reconciliation import (
    RECONCILIATION_VERSION,
    reconcile_final_requirement_matches,
)
from tailoring.phase8_verification import (
    PHASE8_VERIFICATION_VERSION,
    build_phase8_verification,
)


def _row(
    requirement_id: str,
    text: str,
    label: str,
    *,
    importance: str = "required",
) -> dict:
    values = {
        "none": (0.0, 0),
        "weak": (0.2, 2),
        "transferable": (0.55, 3),
        "direct": (1.0, 5),
    }
    match_value, evidence_strength = values[label]
    return {
        "requirement_id": requirement_id,
        "text": text,
        "atomic_focus": text,
        "importance": importance,
        "group_weight_fraction": 1.0,
        "match_label": label,
        "match_value": match_value,
        "evidence_strength": evidence_strength,
        "evidence": [],
    }


def _analysis(rows: list[dict], score: int) -> dict:
    return {
        "canonical_requirements": rows,
        "deterministic_alignment_score": score,
        "required_core_coverage_score": score,
        "preferred_coverage_score": 0,
        "evidence_strength_score": score,
        "score_weights": {
            "required_core_coverage": 0.9,
            "preferred_coverage": 0.0,
            "evidence_strength": 0.1,
        },
    }


def _generation_for_mapping(
    *,
    requirement_id: str,
    requirement_text: str,
    bullet: str,
    mapping_label: str = "direct",
    skills: list[str] | None = None,
) -> dict:
    skill_values = skills or []
    project = {
        "project_id": "project-requestflow",
        "title": "RequestFlow",
        "display_title": "RequestFlow — IT Service Request Tracker",
        "draft_bullets": [bullet],
        "requirement_matches": [
            {
                "requirement_id": requirement_id,
                "requirement_text": requirement_text,
                "match_label": mapping_label,
                "evidence_snippets": [bullet],
            }
        ],
    }
    skill_rankings = [
        {
            "skill": skill,
            "matched_requirement_ids": [requirement_id],
        }
        for skill in skill_values
    ]
    skill_payload = {
        "skill_lines": [{"category": "Tools", "items": skill_values}],
        "skill_rankings": skill_rankings,
    }
    return {
        "projects": {"recommended_projects": [project]},
        "skills": skill_payload,
        "fit_result": {
            "tailored_projects_used": {"recommended_projects": [project]},
            "tailored_skills_used": skill_payload,
        },
    }


def _lineage(*, bullet: str, skills: list[str] | None = None) -> dict:
    return {
        "verified_project_bullets": [
            {
                "project_id": "project-requestflow",
                "project": "RequestFlow — IT Service Request Tracker",
                "bullet": bullet,
                "supported": True,
            }
        ],
        "verified_skills": [
            {
                "category": "Tools",
                "skill": skill,
                "supported": True,
            }
            for skill in (skills or [])
        ],
    }


def _phase8_full_generation(
    *,
    requirement_id: str,
    requirement_text: str,
    bullet: str,
    skills: list[str] | None = None,
) -> dict:
    skill_values = list(skills or [])
    generation = _generation_for_mapping(
        requirement_id=requirement_id,
        requirement_text=requirement_text,
        bullet=bullet,
        skills=skill_values,
    )
    generation.update(
        {
            "application_id": 7,
            "generation_id": "synthetic-htx-phase8-generation",
            "status": "draft",
            "updated_at": "2026-09-10T00:00:00",
            "candidate_pool": [
                {
                    "project_id": "project-requestflow",
                    "title": "RequestFlow",
                    "display_title": (
                        "RequestFlow — IT Service Request Tracker"
                    ),
                    "evidence_records": [
                        {"kind": "bullet", "text": bullet},
                        *[
                            {"kind": "tool", "text": skill}
                            for skill in skill_values
                        ],
                    ],
                }
            ],
        }
    )
    generation["fit_result"].update(
        {
            "fit_one_page": True,
            "page_count": 1,
        }
    )
    return generation


def _phase8_baseline(
    *,
    requirement_id: str,
    requirement_text: str,
    label: str = "direct",
    score: int = 100,
) -> dict:
    stable = _analysis(
        [_row(requirement_id, requirement_text, label)],
        score,
    )
    stable.update(
        {
            "scoring_version": SCORING_VERSION,
            "alignment_band": "strong alignment",
            "input_fingerprint": "synthetic-htx-baseline",
        }
    )
    return {
        "stable_analysis": stable,
        "resume_profile": {
            "projects": [],
            "skills": {},
            "experience": [],
            "education": [],
        },
        "jd_profile": {},
        "keyword_match": {
            "present": [],
            "missing": [],
        },
        "bullets": {"bullet_quality_avg": 80},
        "structure": {"structure_score": 100},
    }


def _phase8_mock_analysis(
    *,
    requirement_id: str,
    requirement_text: str,
    label: str,
    score: int,
) -> dict:
    stable = _analysis(
        [_row(requirement_id, requirement_text, label)],
        score,
    )
    stable.update(
        {
            "scoring_version": SCORING_VERSION,
            "alignment_band": "partial alignment",
            "input_fingerprint": "synthetic-htx-raw-after",
        }
    )
    return stable


class Phase8ScoringCorrectnessTests(unittest.TestCase):
    def test_non_requirement_boilerplate_is_filtered_but_real_contract_skill_survives(self):
        raw_jd = """
What we are looking for
Experience managing customer contracts.
All new hires are appointed on a two-year contract in the first instance and will be assessed and considered for permanent tenure over time, based on performance.
As part of the shortlisting process for this role, you may be required to complete a medical declaration and/or undergo further assessment.
All applicants will be updated on the status of their applications within 4 weeks upon closing of the advertisement.
#LI-HL1
"""
        result = canonicalise_requirements({}, raw_jd)
        texts = [row["text"] for row in result["requirements"]]
        joined = "\n".join(texts).lower()

        self.assertIn("Experience managing customer contracts", texts)
        self.assertNotIn("#li-hl1", joined)
        self.assertNotIn("applicants will be updated", joined)
        self.assertNotIn("medical declaration", joined)
        self.assertNotIn("two-year contract", joined)

        reasons = {
            row["reason"]
            for row in result["filtered_non_requirement_rows"]
        }
        self.assertEqual(
            reasons,
            {
                "recruiter_tracking_tag",
                "application_status_notice",
                "candidate_screening_process",
                "employment_terms_notice",
            },
        )

    def test_certification_requires_explicit_credential_evidence(self):
        requirement = {
            "text": (
                "Relevant Cloud or Kubernetes certifications "
                "(e.g., CKA, CKAD, CKS) are highly preferred"
            ),
            "atomic_focus": (
                "Relevant Cloud or Kubernetes certifications "
                "(e.g., CKA, CKAD, CKS) are highly preferred"
            ),
        }

        usage_only = evaluate_evidence(
            requirement,
            "Created Kubernetes Deployments and configured Ingress.",
        )
        explicit = evaluate_evidence(
            requirement,
            "Certified Kubernetes Administrator (CKA).",
        )

        self.assertEqual(
            usage_only["capability_id"],
            "credential.certification",
        )
        self.assertEqual(usage_only["label"], "none")
        self.assertEqual(explicit["label"], "direct")

    def test_normal_kubernetes_requirement_still_accepts_deployment_evidence(self):
        result = evaluate_evidence(
            {
                "text": "Experience deploying applications with Kubernetes",
                "atomic_focus": "Experience deploying applications with Kubernetes",
            },
            "Created Kubernetes Deployments and configured Ingress.",
        )
        self.assertEqual(result["capability_id"], "devops.kubernetes")
        self.assertEqual(result["label"], "direct")

    def test_fresh_scorer_does_not_turn_kubernetes_usage_into_certification(self):
        requirement_text = (
            "Relevant Cloud or Kubernetes certifications "
            "(e.g., CKA, CKAD, CKS) are highly preferred"
        )
        profile = {
            "projects": [
                {
                    "title": "RequestFlow",
                    "bullets": [
                        "Created Kubernetes Deployments and configured Ingress."
                    ],
                }
            ],
            "experience": [],
            "education": [],
            "skills": {"Tools": ["Kubernetes"]},
        }
        result = build_fresh_target_analysis(
            jd_profile={
                "required_skills": [],
                "responsibilities": [],
                "soft_skills": [],
                "preferred_skills": [requirement_text],
                "deal_breakers": [],
                "tools_technologies": [],
            },
            keyword_match={"present": [], "missing": []},
            resume_profile=profile,
            raw_resume_text="Kubernetes",
        )
        row = next(
            row
            for row in result["canonical_requirements"]
            if "certifications" in row["text"].lower()
        )
        self.assertEqual(row["capability_id"], "credential.certification")
        self.assertEqual(row["match_label"], "none")

    def test_security_in_ci_cd_survives_phase8_when_verified_evidence_is_direct(self):
        requirement_id = "req-security-ci"
        requirement_text = (
            "DevSecOps practices integrating security into CI/CD pipelines"
        )
        bullet = (
            "Added Trivy scanning for frontend and backend images, configuring "
            "CI to fail on fixable HIGH or CRITICAL container vulnerabilities."
        )
        generation = _generation_for_mapping(
            requirement_id=requirement_id,
            requirement_text=requirement_text,
            bullet=bullet,
            skills=["GitHub Actions", "CI/CD"],
        )

        reconciled, report = reconcile_final_requirement_matches(
            before_analysis=_analysis(
                [_row(requirement_id, requirement_text, "direct")],
                100,
            ),
            after_analysis=_analysis(
                [_row(requirement_id, requirement_text, "weak")],
                20,
            ),
            generation_state=generation,
            claim_lineage=_lineage(
                bullet=bullet,
                skills=["GitHub Actions", "CI/CD"],
            ),
        )

        row = reconciled["canonical_requirements"][0]
        self.assertEqual(row["match_label"], "direct")
        self.assertEqual(report["unresolved_regression_count"], 0)
        self.assertEqual(
            row["phase8_reconciliation"]["mapping_support"][
                "semantic_support"
            ]["capability_id"],
            "security.ci_cd",
        )
        self.assertEqual(
            row["phase8_reconciliation"]["mapping_support"][
                "semantic_support"
            ]["label"],
            "direct",
        )

    def test_generic_github_actions_does_not_prove_security_in_ci_cd(self):
        requirement_id = "req-security-ci"
        requirement_text = (
            "DevSecOps practices integrating security into CI/CD pipelines"
        )
        bullet = "Automated builds and tests with GitHub Actions."
        generation = _generation_for_mapping(
            requirement_id=requirement_id,
            requirement_text=requirement_text,
            bullet=bullet,
            skills=["GitHub Actions"],
        )

        reconciled, report = reconcile_final_requirement_matches(
            before_analysis=_analysis(
                [_row(requirement_id, requirement_text, "direct")],
                100,
            ),
            after_analysis=_analysis(
                [_row(requirement_id, requirement_text, "none")],
                0,
            ),
            generation_state=generation,
            claim_lineage=_lineage(
                bullet=bullet,
                skills=["GitHub Actions"],
            ),
        )

        self.assertEqual(
            reconciled["canonical_requirements"][0]["match_label"],
            "none",
        )
        self.assertEqual(report["unresolved_regression_count"], 1)

    def test_existing_genuine_regression_still_blocks(self):
        requirement_id = "req-outage"
        requirement_text = "Managed global production outages for five years"
        bullet = "Built a React help-desk interface."
        generation = _generation_for_mapping(
            requirement_id=requirement_id,
            requirement_text=requirement_text,
            bullet=bullet,
        )

        reconciled, report = reconcile_final_requirement_matches(
            before_analysis=_analysis(
                [_row(requirement_id, requirement_text, "direct")],
                100,
            ),
            after_analysis=_analysis(
                [_row(requirement_id, requirement_text, "none")],
                0,
            ),
            generation_state=generation,
            claim_lineage=_lineage(bullet=bullet),
        )

        self.assertEqual(
            reconciled["canonical_requirements"][0]["match_label"],
            "none",
        )
        self.assertEqual(report["unresolved_regression_count"], 1)

    def test_htx_regression_fixture_has_consistent_semantics(self):
        raw_jd = """
What we are looking for
Experience deploying applications with Kubernetes.
DevSecOps practices integrating security into CI/CD pipelines.
Relevant Cloud or Kubernetes certifications (e.g., CKA, CKAD, CKS) are highly preferred.
All new hires are appointed on a two-year contract in the first instance and will be assessed and considered for permanent tenure over time, based on performance.
As part of the shortlisting process for this role, you may be required to complete a medical declaration and/or undergo further assessment.
All applicants will be updated on the status of their applications within 4 weeks upon closing of the advertisement.
#LI-HL1
"""
        canonical = canonicalise_requirements({}, raw_jd)
        canonical_text = "\n".join(
            row["text"] for row in canonical["requirements"]
        ).lower()
        self.assertNotIn("#li-hl1", canonical_text)
        self.assertNotIn("medical declaration", canonical_text)
        self.assertNotIn("applicants will be updated", canonical_text)
        self.assertNotIn("two-year contract", canonical_text)

        cert = evaluate_evidence(
            {
                "text": (
                    "Relevant Cloud or Kubernetes certifications "
                    "(e.g., CKA, CKAD, CKS) are highly preferred"
                ),
                "atomic_focus": (
                    "Relevant Cloud or Kubernetes certifications "
                    "(e.g., CKA, CKAD, CKS) are highly preferred"
                ),
            },
            "Created Kubernetes Deployments and configured Ingress.",
        )
        self.assertEqual(cert["label"], "none")

        security = evaluate_evidence(
            {
                "text": (
                    "DevSecOps practices integrating security into CI/CD pipelines"
                ),
                "atomic_focus": (
                    "DevSecOps practices integrating security into CI/CD pipelines"
                ),
            },
            (
                "Added Trivy scanning for frontend and backend images, "
                "configuring CI to fail on fixable HIGH or CRITICAL "
                "container vulnerabilities."
            ),
        )
        self.assertEqual(security["capability_id"], "security.ci_cd")
        self.assertEqual(security["label"], "direct")

    def test_end_to_end_delivery_capability_preserves_partial_working_app_evidence(self):
        requirement = {
            "text": (
                "Experience taking a software project from initial setup "
                "to a working user-facing application"
            ),
            "atomic_focus": (
                "Experience taking a software project from initial setup "
                "to a working user-facing application"
            ),
        }

        partial = evaluate_evidence(
            requirement,
            "Built a full-stack help-desk workflow in a 4-person team.",
        )
        direct = evaluate_evidence(
            requirement,
            (
                "Set up the project environment and delivered a working "
                "full-stack application with frontend and backend integration."
            ),
        )

        self.assertEqual(
            partial["capability_id"],
            "delivery.end_to_end_application",
        )
        self.assertEqual(partial["label"], "transferable")
        self.assertEqual(direct["label"], "direct")

    def test_htx_full_phase8_false_regression_is_reconciled(self):
        from unittest.mock import patch

        raw_jd = """
What we are looking for
Experience managing customer contracts.
Experience deploying applications with Kubernetes.
DevSecOps practices integrating security into CI/CD pipelines.
Relevant Cloud or Kubernetes certifications (e.g., CKA, CKAD, CKS) are highly preferred.
All new hires are appointed on a two-year contract in the first instance and will be assessed and considered for permanent tenure over time, based on performance.
As part of the shortlisting process for this role, you may be required to complete a medical declaration and/or undergo further assessment.
All applicants will be updated on the status of their applications within 4 weeks upon closing of the advertisement.
#LI-HL1
"""
        canonical = canonicalise_requirements({}, raw_jd)
        canonical_rows = canonical["requirements"]
        canonical_texts = [row["text"] for row in canonical_rows]
        canonical_joined = "\n".join(canonical_texts).lower()

        self.assertIn(
            "Experience managing customer contracts",
            canonical_texts,
        )
        self.assertNotIn("#li-hl1", canonical_joined)
        self.assertNotIn("applicants will be updated", canonical_joined)
        self.assertNotIn("medical declaration", canonical_joined)
        self.assertNotIn("two-year contract", canonical_joined)

        security_row = next(
            row
            for row in canonical_rows
            if "devsecops practices" in row["text"].lower()
        )
        certification_row = next(
            row
            for row in canonical_rows
            if "kubernetes certifications" in row["text"].lower()
        )

        kubernetes_usage = (
            "Created Kubernetes Deployments and configured Ingress."
        )
        cert_usage_only = evaluate_evidence(
            {
                "text": certification_row["text"],
                "atomic_focus": certification_row["text"],
            },
            kubernetes_usage,
        )
        cert_explicit = evaluate_evidence(
            {
                "text": certification_row["text"],
                "atomic_focus": certification_row["text"],
            },
            "Certified Kubernetes Administrator (CKA).",
        )
        self.assertEqual(
            cert_usage_only["capability_id"],
            "credential.certification",
        )
        self.assertEqual(cert_usage_only["label"], "none")
        self.assertEqual(cert_explicit["label"], "direct")

        trivy_bullet = (
            "Added Trivy scanning for frontend and backend images, "
            "configuring CI to fail on fixable HIGH or CRITICAL "
            "container vulnerabilities."
        )
        security_semantics = evaluate_evidence(
            {
                "text": security_row["text"],
                "atomic_focus": security_row["text"],
            },
            trivy_bullet,
        )
        self.assertEqual(
            security_semantics["capability_id"],
            "security.ci_cd",
        )
        self.assertEqual(security_semantics["label"], "direct")

        requirement_id = security_row["requirement_id"]
        requirement_text = security_row["text"]
        baseline = _phase8_baseline(
            requirement_id=requirement_id,
            requirement_text=requirement_text,
        )
        generation = _phase8_full_generation(
            requirement_id=requirement_id,
            requirement_text=requirement_text,
            bullet=trivy_bullet,
            skills=["GitHub Actions", "CI/CD"],
        )
        raw_after = _phase8_mock_analysis(
            requirement_id=requirement_id,
            requirement_text=requirement_text,
            label="weak",
            score=20,
        )

        with patch(
            "tailoring.phase8_verification.build_stable_analysis",
            return_value=raw_after,
        ) as mocked_build:
            result = build_phase8_verification(
                baseline_report=baseline,
                generation_state=generation,
                raw_jd_text=raw_jd,
            )

        self.assertEqual(mocked_build.call_count, 1)
        self.assertEqual(
            len(
                result["raw_comparison_before_reconciliation"][
                    "important_regressions"
                ]
            ),
            1,
        )
        reconciled_row = result["after_stable_analysis"][
            "canonical_requirements"
        ][0]
        self.assertEqual(reconciled_row["match_label"], "direct")
        self.assertEqual(
            result["requirement_reconciliation"][
                "unresolved_regression_count"
            ],
            0,
        )
        self.assertFalse(result["comparison"]["important_regressions"])
        self.assertEqual(
            result["claim_lineage"]["claim_review_required_count"],
            0,
        )
        self.assertTrue(
            result["approval_readiness_reasons"][
                "no_required_core_regression"
            ]
        )
        self.assertTrue(result["approval_ready"])
        self.assertFalse(result["blueprint_ready"])
        self.assertIn(result["verdict"], {"maintained", "improved"})

    def test_htx_full_phase8_negative_control_still_blocks(self):
        from unittest.mock import patch

        requirement_id = "req-outage"
        requirement_text = (
            "Managed global production outages for five years"
        )
        unrelated_bullet = "Built a React help-desk interface."

        baseline = _phase8_baseline(
            requirement_id=requirement_id,
            requirement_text=requirement_text,
        )
        generation = _phase8_full_generation(
            requirement_id=requirement_id,
            requirement_text=requirement_text,
            bullet=unrelated_bullet,
        )
        raw_after = _phase8_mock_analysis(
            requirement_id=requirement_id,
            requirement_text=requirement_text,
            label="none",
            score=0,
        )

        with patch(
            "tailoring.phase8_verification.build_stable_analysis",
            return_value=raw_after,
        ):
            result = build_phase8_verification(
                baseline_report=baseline,
                generation_state=generation,
                raw_jd_text=(
                    "Requirements\n"
                    "Managed global production outages for five years."
                ),
            )

        reconciled_row = result["after_stable_analysis"][
            "canonical_requirements"
        ][0]
        self.assertEqual(reconciled_row["match_label"], "none")
        self.assertEqual(
            result["requirement_reconciliation"][
                "unresolved_regression_count"
            ],
            1,
        )
        self.assertEqual(
            len(result["comparison"]["important_regressions"]),
            1,
        )
        self.assertEqual(
            result["claim_lineage"]["claim_review_required_count"],
            0,
        )
        self.assertFalse(
            result["approval_readiness_reasons"][
                "no_required_core_regression"
            ]
        )
        self.assertFalse(result["approval_ready"])
        self.assertEqual(result["verdict"], "regression_detected")

    def test_versions_are_bumped_for_saved_result_invalidation(self):
        self.assertEqual(SCORING_VERSION, "stable-evidence-v1.4-phase6d8")
        self.assertEqual(
            get_default_taxonomy().version,
            "phase6d-capability-taxonomy-v1.3",
        )
        self.assertEqual(
            RECONCILIATION_VERSION,
            "phase8-final-evidence-reconciliation-v3",
        )
        self.assertEqual(
            PHASE8_VERIFICATION_VERSION,
            "phase8-before-after-verification-v9",
        )


if __name__ == "__main__":
    unittest.main()
