from __future__ import annotations

import unittest
from unittest.mock import patch

from database import phase9f_tailoring_execution_manager as manager


class ApplicationSessionJDRephraseTests(unittest.TestCase):
    def _source(self, status="draft"):
        return {
            "generation_id": "ordinary-a",
            "status": status,
            "generation_kind": "projects_skills",
            "input_fingerprint": "input-a",
            "generation_settings": {"max_projects": 3},
            "candidate_pool": [{"project_id": "p1", "title": "CyberSphere"}],
            "project_inputs": {"evidence_items": [{"project_id": "p1"}]},
            "projects": {
                "recommended_projects": [
                    {
                        "project_id": "p1",
                        "title": "CyberSphere",
                        "display_title": "CyberSphere — Shooter Game",
                        "draft_bullets": [
                            "Built gameplay and UI features for a mobile game."
                        ],
                        "selected_blueprint_bullets": [
                            "Built gameplay and UI features for a mobile game."
                        ],
                    }
                ]
            },
            "skills": {"skill_lines": []},
            "fit_result": {"fit_one_page": True},
            "docx_path": "old.docx",
            "pdf_path": "old.pdf",
            "base_content_fingerprint": "base-a",
            "phase9e_decision_fingerprint": "",
        }

    def test_ordinary_draft_creates_unfitted_child_without_phase9f_prepare(self):
        source = self._source()
        proposed = {
            **source,
            "projects": {
                "recommended_projects": [
                    {
                        **source["projects"]["recommended_projects"][0],
                        "draft_bullets": [
                            "Built gameplay and UI features for a published mobile game."
                        ],
                        "compact_bullets": [],
                    }
                ]
            },
            "fit_result": None,
            "docx_path": "",
            "pdf_path": "",
        }
        saved = {}

        def save_generation(**kwargs):
            saved["save"] = kwargs

        def get_generation(_application_id, generation_id):
            if generation_id == "ordinary-a":
                return source
            if generation_id == saved.get("save", {}).get("generation_id"):
                return {**saved["save"], "generation_id": generation_id, "status": "draft"}
            return None

        with patch.object(manager, "get_tailoring_generation", side_effect=get_generation),              patch.object(manager.db_manager, "get_application_by_id", return_value={
                 "report": {
                     "jd_profile": {"responsibilities": ["Support game QA."]},
                     "raw_jd_text": "Support game QA.",
                     "resume_profile": {},
                 }
             }),              patch.object(manager, "evaluate_rephrase_candidate", return_value={
                 "safe_to_accept": True,
                 "proposed_generation": proposed,
                 "fresh_score_comparison": {"available": True, "score_delta": 0},
             }),              patch.object(manager, "save_application_tailoring_generation", side_effect=save_generation),              patch.object(manager, "record_generation_metadata") as record_meta,              patch.object(manager, "prepare_or_reuse_phase9f_tailoring_execution") as prepare_f:
            result = manager.create_application_jd_rephrase_generation(
                application_id=7,
                source_generation_id="ordinary-a",
                project_index=0,
                bullet_index=0,
                accepted_bullet=(
                    "Built gameplay and UI features for a published mobile game."
                ),
                suggestion_model="model-a",
            )

        prepare_f.assert_not_called()
        self.assertEqual(
            result["cache_status"],
            "application_jd_rephrase_generation_created",
        )
        self.assertEqual(saved["save"]["docx_path"], "")
        self.assertEqual(saved["save"]["pdf_path"], "")
        self.assertEqual(saved["save"]["fit_result"], {})
        kwargs = record_meta.call_args.kwargs
        self.assertEqual(kwargs["parent_generation_id"], "ordinary-a")
        self.assertEqual(
            kwargs["generation_kind"],
            manager.APPLICATION_SESSION_REPHRASE_KIND,
        )

    def test_approved_ordinary_generation_requires_workspace_revision_first(self):
        with patch.object(
            manager,
            "get_tailoring_generation",
            return_value=self._source(status="approved"),
        ):
            with self.assertRaises(manager.Phase9FFExecutionError) as raised:
                manager.create_application_jd_rephrase_generation(
                    application_id=7,
                    source_generation_id="ordinary-a",
                    project_index=0,
                    bullet_index=0,
                    accepted_bullet="Different supported wording.",
                )
        self.assertEqual(
            raised.exception.code,
            "jd_rephrase_editable_draft_required",
        )


if __name__ == "__main__":
    unittest.main()
