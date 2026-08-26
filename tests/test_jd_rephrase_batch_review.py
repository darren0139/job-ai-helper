from __future__ import annotations

import unittest
from copy import deepcopy
from unittest.mock import patch

import llm
from database import phase9f_tailoring_execution_manager as manager
from tailoring import jd_specific_rephrase_preview as preview


class RephraseModelRouteTests(unittest.TestCase):
    def test_rephrase_route_accepts_local_qwen(self):
        original = llm.get_active_model("rephrase")
        try:
            selected = llm.set_runtime_model(
                "ollama/qwen3:14b",
                route="rephrase",
            )
            self.assertEqual(selected, "ollama/qwen3:14b")
            self.assertEqual(
                llm.get_active_model("rephrase"),
                "ollama/qwen3:14b",
            )
            self.assertIn(
                "ollama/qwen3:14b",
                llm.get_model_options().values(),
            )
        finally:
            llm.set_runtime_model(original, route="rephrase")


class BatchPreviewTests(unittest.TestCase):
    def _generation(self):
        return {
            "generation_id": "g1",
            "projects": {
                "recommended_projects": [
                    {
                        "project_id": "p1",
                        "title": "Project One",
                        "display_title": "Project One — App",
                        "draft_bullets": [
                            "Built a Python application for workflow automation.",
                            "Added automated tests for the application.",
                        ],
                        "selected_blueprint_bullets": [
                            "Built a Python application for workflow automation.",
                            "Added automated tests for the application.",
                        ],
                        "compact_bullets": ["old compact"],
                    }
                ]
            },
            "skills": {"skill_lines": ["Programming: Python"]},
            "candidate_pool": [{"project_id": "p1", "title": "Project One"}],
            "project_inputs": {"evidence_items": [{"project_id": "p1"}]},
            "fit_result": {"page_count": 1},
            "docx_path": "old.docx",
            "pdf_path": "old.pdf",
        }

    def test_batch_candidate_changes_two_bullets_and_preserves_header(self):
        generation = self._generation()
        before = deepcopy(
            generation["projects"]["recommended_projects"][0]
        )
        candidate = preview.build_rephrased_generation_batch_candidate(
            generation=generation,
            accepted_changes=[
                {
                    "project_index": 0,
                    "bullet_index": 0,
                    "accepted_bullet": (
                        "Built a Python application integrating workflow automation."
                    ),
                },
                {
                    "project_index": 0,
                    "bullet_index": 1,
                    "accepted_bullet": (
                        "Added automated tests supporting application reliability."
                    ),
                },
            ],
        )
        project = candidate["projects"]["recommended_projects"][0]
        self.assertEqual(project["title"], before["title"])
        self.assertEqual(project["display_title"], before["display_title"])
        self.assertEqual(len(project["draft_bullets"]), 2)
        self.assertEqual(project["compact_bullets"], [])
        self.assertIsNone(candidate["fit_result"])
        self.assertEqual(candidate["docx_path"], "")
        self.assertEqual(candidate["pdf_path"], "")
        self.assertEqual(
            generation["projects"]["recommended_projects"][0]["draft_bullets"][0],
            "Built a Python application for workflow automation.",
        )

    def test_batch_suggestion_is_one_model_call_surface_for_all_contexts(self):
        generation = self._generation()
        contexts = preview.build_rephrase_batch_contexts(
            generation=generation,
            baseline_report={
                "jd_profile": {"responsibilities": ["Integrate software."]},
                "raw_jd_text": "Integrate software.",
            },
            project_indices=[0],
        )
        with patch.object(
            preview,
            "ask_json",
            return_value={
                "suggestions": [
                    {
                        "project_index": 0,
                        "bullet_index": 0,
                        "suggested_bullet": (
                            "Built a Python application integrating workflow automation."
                        ),
                        "reason": "Emphasizes integration.",
                        "jd_terms_used": ["integration"],
                        "evidence_preserved": True,
                    },
                    {
                        "project_index": 0,
                        "bullet_index": 1,
                        "suggested_bullet": (
                            "Added automated tests for the application."
                        ),
                        "reason": "Keep current wording.",
                        "jd_terms_used": [],
                        "evidence_preserved": True,
                    },
                ]
            },
        ) as ask:
            result = preview.suggest_jd_specific_rephrases_batch(
                contexts=contexts,
                model="ollama/qwen3:14b",
            )
        self.assertEqual(ask.call_count, 1)
        self.assertEqual(len(result["suggestions"]), 2)
        self.assertEqual(ask.call_args.kwargs["route"], "rephrase")
        self.assertEqual(
            ask.call_args.kwargs["model"],
            "ollama/qwen3:14b",
        )


class BatchPersistenceTests(unittest.TestCase):
    def test_ordinary_session_batch_creates_one_unfitted_child(self):
        source = {
            "generation_id": "ordinary-a",
            "status": "draft",
            "generation_settings": {},
            "input_fingerprint": "input-a",
            "candidate_pool": [],
            "project_inputs": {},
            "projects": {
                "recommended_projects": [
                    {
                        "project_id": "p1",
                        "title": "Project One",
                        "draft_bullets": ["Bullet one.", "Bullet two."],
                    }
                ]
            },
            "skills": {"skill_lines": []},
            "base_content_fingerprint": "base-a",
            "phase9e_decision_fingerprint": "",
        }
        proposed = deepcopy(source)
        proposed["projects"]["recommended_projects"][0]["draft_bullets"] = [
            "Changed bullet one.",
            "Changed bullet two.",
        ]
        proposed["fit_result"] = None
        proposed["docx_path"] = ""
        proposed["pdf_path"] = ""
        saved = {}

        def save_generation(**kwargs):
            saved["row"] = kwargs

        def get_generation(_application_id, generation_id):
            if generation_id == "ordinary-a":
                return source
            if generation_id == saved.get("row", {}).get("generation_id"):
                return {
                    **saved["row"],
                    "generation_id": generation_id,
                    "status": "draft",
                }
            return None

        with patch.object(
            manager,
            "get_tailoring_generation",
            side_effect=get_generation,
        ), patch.object(
            manager.db_manager,
            "get_application_by_id",
            return_value={
                "report": {
                    "jd_profile": {"responsibilities": ["Integrate software"]},
                    "raw_jd_text": "Integrate software",
                    "resume_profile": {},
                }
            },
        ), patch.object(
            manager,
            "evaluate_rephrase_batch_candidate",
            return_value={
                "safe_to_accept": True,
                "proposed_generation": proposed,
                "fresh_score_comparison": {"available": True},
            },
        ), patch.object(
            manager,
            "save_application_tailoring_generation",
            side_effect=save_generation,
        ) as save_call, patch.object(
            manager,
            "record_generation_metadata",
        ):
            result = manager.create_application_jd_rephrase_batch_generation(
                application_id=7,
                source_generation_id="ordinary-a",
                accepted_changes=[
                    {
                        "project_index": 0,
                        "bullet_index": 0,
                        "accepted_bullet": "Changed bullet one.",
                    },
                    {
                        "project_index": 0,
                        "bullet_index": 1,
                        "accepted_bullet": "Changed bullet two.",
                    },
                ],
                suggestion_model="ollama/qwen3:14b",
            )

        self.assertEqual(save_call.call_count, 1)
        self.assertEqual(saved["row"]["docx_path"], "")
        self.assertEqual(saved["row"]["pdf_path"], "")
        self.assertEqual(saved["row"]["fit_result"], {})
        self.assertEqual(
            result["cache_status"],
            "application_jd_rephrase_batch_generation_created",
        )


if __name__ == "__main__":
    unittest.main()
