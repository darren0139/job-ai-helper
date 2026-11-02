"""Adaptive Projects V3: source-backed count and fit-only selection tests."""
import unittest
from copy import deepcopy
from tailoring.adaptive_project_selection_v3 import (
    MAX_PROJECTS,
    POLICY_VERSION,
    apply_adaptive_project_selection,
    generated_project_options,
    normalise_adaptive_project_settings,
    select_auto_project_count,
)


def _projects():
    rows=[]
    for i,(name,match,score) in enumerate([
        ("C++ Engine", "transferable", 72),
        ("Android", "direct", 92),
        ("Backend", "none", 0),
        ("Shooter", "none", 0),
        ("Job AI Helper", "none", 0),
    ]):
        rows.append({"project_id":f"pid{i}","title":name,"display_title":name,
            "draft_bullets":["Built a factual system.","Tested its behavior."],
            "project_fit_score":score,"requirement_matches":[{"match_label":match}],
            "source":"evidence_library"})
    return {"recommended_projects":rows,"candidate_project_ranking":[{"project_id":p['project_id']} for p in rows]}


def _candidates():
    values=[("C++ Engine", ["C++"], ["Designed engine", "Built asset manager"]),
        ("Android",["Kotlin"],["Built mobile app","Integrated user flows"]),
        ("Backend",["PostgreSQL"],["Created backend","Tested queries"]),
        ("Shooter",["Unity"],["Scripted mechanics","Released game"]),
        ("Job AI Helper",["Streamlit","Python"],["Built test suite","Developed Streamlit UI"])]
    return [{"title":n,"canonical_tools":tools,"evidence_library_evidence":{"bullets":bullets,"tools":tools}}
        for n,tools,bullets in values]


class AdaptiveProjectsV3Tests(unittest.TestCase):
    def test_balanced_preserves_fifth_when_already_generated(self):
        src=_projects();before=deepcopy(src)
        selected=apply_adaptive_project_selection(src,mode="balanced")
        self.assertEqual(len(selected["recommended_projects"]),5)
        self.assertEqual(src,before)
        self.assertEqual(selected["adaptive_fit_selection"]["policy_version"],POLICY_VERSION)
    def test_preserve_all_only_saved_generated(self):
        src=_projects()
        selected=apply_adaptive_project_selection(src,mode="preserve_generated")
        self.assertEqual(len(selected["recommended_projects"]),5)
        self.assertEqual(selected["adaptive_fit_selection"]["source"],"saved_generated_project_bullets_only")
    def test_manual_only_known_generated_ids(self):
        src=_projects();keys=["id:pid0","id:pid4"]
        selected=apply_adaptive_project_selection(src,mode="manual",selected_keys=keys)
        self.assertEqual([row["project_id"] for row in selected["recommended_projects"]],["pid0","pid4"])
        for rejected in (["id:unwritten"], [""], ["id:pid4","id:pid4"],[]):
            with self.assertRaises(ValueError):apply_adaptive_project_selection(src,mode="manual",selected_keys=rejected)
    def test_jd_focus_requires_proven_record(self):
        picked=apply_adaptive_project_selection(_projects(),mode="jd_focused")
        self.assertEqual([r["project_id"] for r in picked["recommended_projects"]],["pid0","pid1"])
        no_jd=_projects()
        for row in no_jd["recommended_projects"]: row["requirement_matches"]=[]
        with self.assertRaisesRegex(ValueError,"No generated project"):
            apply_adaptive_project_selection(no_jd,mode="jd_focused")
    def test_legacy_does_not_require_persisted_bullet_pool(self):
        old={"recommended_projects":[{"title":"Legacy project"}]}
        self.assertEqual(apply_adaptive_project_selection(old,mode="legacy"),old)
        with self.assertRaises(ValueError):apply_adaptive_project_selection(old,mode="balanced")
    def test_original_pool_retained_for_reselection_after_fit(self):
        src=_projects()
        manual=apply_adaptive_project_selection(src,mode="manual",selected_keys=["id:pid1"])
        self.assertEqual(len(manual["recommended_projects"]),1)
        self.assertEqual(len(generated_project_options(manual)),5)
        restored=apply_adaptive_project_selection(manual,mode="preserve_generated")
        self.assertEqual(len(restored["recommended_projects"]),5)
        self.assertEqual(src["recommended_projects"],restored["recommended_projects"])
    def test_no_duplicate_identity_or_missing_bullets(self):
        for alteration in ("duplicate", "missing"):
            data=_projects()
            if alteration=="duplicate":data["recommended_projects"][1]["project_id"]="pid0"
            else:data["recommended_projects"][1]["draft_bullets"]=[]
            with self.assertRaises(ValueError):generated_project_options(data)
    def test_invalid_controls_fail_closed(self):
        for mode in ("", "auto_fit_unimplemented", "preserve_all"):
            with self.assertRaises(ValueError):normalise_adaptive_project_settings(mode)
        for keys in (["unknown"], [3], {"unexpected":True}):
            with self.assertRaises(ValueError):normalise_adaptive_project_settings("balanced", keys)
        self.assertEqual(MAX_PROJECTS,8)
    def test_auto_adds_fifth_when_complementary_canonical_evidence(self):
        c=_candidates();v={"system_selected_projects":[{"title":x["title"]} for x in c]}
        count, reason=select_auto_project_count(c,v)
        self.assertEqual(count,5)
        self.assertIn("Fifth project",reason)
    def test_auto_does_not_pad_without_bullets(self):
        c=_candidates();v={"system_selected_projects":[{"title":x["title"]} for x in c]}
        c[-1]["evidence_library_evidence"]["bullets"]=["Just one bullet"]
        self.assertEqual(select_auto_project_count(c,v)[0],4)
    def test_auto_does_not_pad_without_additional_tools(self):
        c=_candidates();v={"system_selected_projects":[{"title":x["title"]} for x in c]}
        c[-1]["canonical_tools"]=["Unity"]
        c[-1]["evidence_library_evidence"]["tools"]=["Unity"]
        self.assertEqual(select_auto_project_count(c,v)[0],4)
    def test_auto_less_than_five_candidates_is_bounded(self):
        c=_candidates()[:3];v={"system_selected_projects":[{"title":x["title"]} for x in c]}
        self.assertEqual(select_auto_project_count(c,v)[0],3)
    def test_auto_rejects_unrecognized_preview_and_duplicate_sources(self):
        c=_candidates();v={"system_selected_projects":[{"title":x["title"]} for x in c]}
        v["system_selected_projects"][-1]["title"]="fabricated"
        with self.assertRaises(ValueError):select_auto_project_count(c,v)
        c=_candidates();c[1]["title"]=c[0]["title"]
        with self.assertRaises(ValueError):select_auto_project_count(c,{"system_selected_projects":[{"title":x["title"]} for x in c]})
    def test_fitted_selection_preserves_ranking_and_nonmutation(self):
        src=_projects();before=deepcopy(src)
        for mode in ("balanced","preserve_generated","jd_focused"):
            got=apply_adaptive_project_selection(src,mode=mode)
            self.assertEqual(got["candidate_project_ranking"],before["candidate_project_ranking"])
        self.assertEqual(src,before)

if __name__=="__main__":unittest.main()
