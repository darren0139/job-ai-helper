"""Focused source-aligned, non-mutating lead-first tests."""
import copy
import hashlib
import unittest
from pathlib import Path
from unittest.mock import patch

from tailoring.phase9f_lead_intro_v310 import apply_lead_first_prepared, verify_fitted_leads, VERSION

BASE = "Built an AI-assisted Streamlit platform for resume/JD parsing, application sessions, Job Match analysis, and evidence-grounded tailoring."
LIBRARY = "Built a Streamlit job-application assistant that analyzes PDF/DOCX resumes against job descriptions and supports an end-to-end résumé-tailoring workflow."
CI = "Added automated unit tests and GitHub Actions CI across Ubuntu and Windows, running dependency checks, compilation, the full test suite, and a Streamlit startup health check."
PIPELINE = "Engineered a deterministic Job Match pipeline with requirement decomposition, weighted scoring, provenance tracking, and governed capability/technology taxonomy."
QSETUP = "Set up the React and Supabase project environment and connected the frontend to the PostgreSQL-backed service."
QLEAD = "Built full-stack help-desk workflows in a 4-person team using React and Supabase/PostgreSQL, connecting frontend ticket-management features with a secure database-backed service."
QSEC = "Implemented backend data access through PostgREST and applied Row-Level Security policies to secure database operations."


def project(name, bullet_texts, *, provenance=None, points=None, protected=None, compact=None):
    provenance = provenance or {}
    points = points or {}
    protected = protected or set()
    p = {
        "display_title": name, "draft_bullets": list(bullet_texts),
        "bullet_evidence_priorities": [{"bullet_index": i, "bullet_text": b, "evidence_value": points.get(b, 0),
                                         "supported_requirement_ids": [], "protected_requirement_ids": [],
                                         "protect_during_fitting": b in protected} for i, b in enumerate(bullet_texts)],
        "bullet_decision_receipts": [{"bullet": b, "sources": provenance.get(b, [])} for b in bullet_texts],
        "selected_blueprint_bullets": list(bullet_texts),
        "selected_bullet_sources": [provenance.get(b, []) for b in bullet_texts],
        "protected_bullet_indexes": [i for i, b in enumerate(bullet_texts) if b in protected],
        "compact_bullets": list(compact or []),
    }
    return p


def payload(p):
    return {"recommended_projects": [p], "_v39_auto_dedupe": {"version": "v39", "removals": [1]}}


class LeadFirstTests(unittest.TestCase):
    def setUp(self):
        self.name = "Job AI Helper — AI-Powered Resume Tailoring System"
        self.provenance = {BASE: ["base"], LIBRARY: ["library"], CI: ["library"], PIPELINE: ["base"]}

    def test_two_steam_intro_sources_deduped_base_selected_for_breadth(self):
        p = project(self.name, [CI, LIBRARY, PIPELINE, BASE], provenance=self.provenance)
        original = payload(p)
        saved = copy.deepcopy(original)
        result = apply_lead_first_prepared(original)
        self.assertEqual(original, saved)
        out = result["recommended_projects"][0]
        self.assertEqual(out["draft_bullets"], [BASE, CI, PIPELINE])
        self.assertEqual(len(result["_v310_lead_intro"]["removals"]), 1)
        self.assertEqual(result["_v310_lead_intro"]["removals"][0]["removed"], LIBRARY)
        self.assertEqual([r["bullet_index"] for r in out["bullet_evidence_priorities"]], [0, 1, 2])
        self.assertEqual([r["bullet_text"] for r in out["bullet_evidence_priorities"]], out["draft_bullets"])
        self.assertEqual(out["protected_bullet_indexes"], [0])
        self.assertTrue(out["bullet_evidence_priorities"][0]["protect_during_fitting"])
        self.assertEqual(out["selected_blueprint_bullets"], p["selected_blueprint_bullets"])
        self.assertEqual(out["selected_bullet_sources"], p["selected_bullet_sources"])
        self.assertEqual(result["_v39_auto_dedupe"], original["_v39_auto_dedupe"])

    def test_queryai_uses_overview_not_setup(self):
        p = project("QueryAI — AI-Powered Help Desk App", [QSETUP, QSEC, QLEAD],
                    provenance={QSETUP: ["base", "library"], QSEC: ["library"], QLEAD: ["library"]})
        out = apply_lead_first_prepared(payload(p))
        b = out["recommended_projects"][0]["draft_bullets"]
        self.assertEqual(b, [QLEAD, QSETUP, QSEC])
        self.assertEqual(out["_v310_lead_intro"]["removals"], [])

    def test_cplusplus_asset_manager_not_game_intro(self):
        text = "Built a C++ asset manager for a custom game engine, centralising asset loading and improving pipeline consistency."
        r = apply_lead_first_prepared(payload(project("The Great Migration — Survival Game", [text, "Integrated FMOD into gameplay systems."])))
        self.assertEqual(r["recommended_projects"][0]["draft_bullets"][0], text)
        self.assertEqual(r["_v310_lead_intro"]["projects"][0]["status"], "no_grounded_product_introduction")

    def test_builtin_pipeline_not_intro(self):
        r = apply_lead_first_prepared(payload(project(self.name, [PIPELINE, CI])))
        self.assertEqual(r["_v310_lead_intro"]["removals"], [])
        self.assertEqual(r["_v310_lead_intro"]["projects"][0]["status"], "no_grounded_product_introduction")

    def test_no_cross_source_provenance_no_removal(self):
        p = project(self.name, [LIBRARY, BASE, CI], provenance={BASE: ["base"], LIBRARY: ["base"], CI: ["library"]})
        r = apply_lead_first_prepared(payload(p))
        self.assertEqual(len(r["recommended_projects"][0]["draft_bullets"]), 3)
        self.assertEqual(r["_v310_lead_intro"]["removals"], [])
        self.assertEqual(r["_v310_lead_intro"]["projects"][0]["unresolved_intro_count"], 1)

    def test_distinct_product_intro_preserved(self):
        different = "Built a Streamlit shopping dashboard that tracks orders and generates stock reports."
        p = project(self.name, [LIBRARY, different], provenance={LIBRARY: ["base"], different: ["library"]})
        r = apply_lead_first_prepared(payload(p))
        self.assertEqual(len(r["recommended_projects"][0]["draft_bullets"]), 2)

    def test_metadata_stale_indexes_rebuilt_by_exact_text(self):
        p = project(self.name, [CI, LIBRARY, BASE], provenance=self.provenance,
                    points={CI: 9, LIBRARY: 0, BASE: 0}, protected={CI})
        for row in p["bullet_evidence_priorities"]: row["bullet_index"] += 17
        r = apply_lead_first_prepared(payload(p))
        out = r["recommended_projects"][0]
        self.assertEqual([r["bullet_text"] for r in out["bullet_evidence_priorities"]], out["draft_bullets"])
        self.assertEqual(out["protected_bullet_indexes"], [0, 1])
        self.assertEqual(out["bullet_evidence_priorities"][1]["evidence_value"], 9)

    def test_missing_matching_metadata_held_not_miscredited(self):
        p = project(self.name, [CI, LIBRARY, BASE], provenance=self.provenance)
        p["bullet_evidence_priorities"].pop(1)
        original = copy.deepcopy(p)
        r = apply_lead_first_prepared(payload(p))
        self.assertEqual(r["recommended_projects"][0], original)
        self.assertEqual(r["_v310_lead_intro"]["projects"][0]["status"], "metadata_not_aligned")

    def test_compact_index_alignment_and_lead_protection(self):
        p = project(self.name, [LIBRARY, CI, BASE], provenance=self.provenance,
                    compact=[LIBRARY + " short", CI + " short", BASE + " short"])
        out = apply_lead_first_prepared(payload(p))["recommended_projects"][0]
        self.assertEqual(out["compact_bullets"], [BASE, CI + " short"])

    def test_locks_are_read_only_and_separate(self):
        p = payload(project(self.name, [CI, LIBRARY, BASE], provenance=self.provenance))
        out = apply_lead_first_prepared(p, enabled=False)
        self.assertEqual(out["recommended_projects"], p["recommended_projects"])
        self.assertEqual(out["_v310_lead_intro"]["status"], "projects_locked")

    def test_repeated_call_no_extra_duplicates(self):
        p = payload(project(self.name, [CI, LIBRARY, BASE], provenance=self.provenance))
        a = apply_lead_first_prepared(p)
        b = apply_lead_first_prepared(a)
        self.assertEqual(a["recommended_projects"], b["recommended_projects"])
        self.assertEqual(b["_v310_lead_intro"]["removals"], [])

    def test_readback_unverified_if_no_one_page(self):
        r = verify_fitted_leads({"v310_lead_intro": {"version": VERSION}, "fit_one_page": False}, repo_root=Path("."), application_id=156)
        self.assertEqual(r["status"], "unverified")

    def test_version_report_stable(self):
        self.assertTrue(VERSION.startswith("phase9f-v310"))
        self.assertEqual(hashlib.sha256(BASE.encode()).digest_size, 32)


if __name__ == "__main__":
    unittest.main()
