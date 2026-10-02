"""Temporary production knowledge and fake focused verification for v1.7 checks."""
from __future__ import annotations

import json
import os
import sys
from types import ModuleType
import tempfile
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import Mock, patch

from database import job_match_manager
from database.technology_registry_proposal_manager import (
    import_proposal_bundle, list_proposals, list_proposal_reviews, save_proposal_review, publish_approved_proposal,
)
from taxonomy_discovery import technology_registry as production
from taxonomy_discovery.focused_verification import execute_focused_verification, interpret_focused_verification, build_focused_draft
from taxonomy_discovery.focused_verification_targets import build_focused_verification_target
from tailoring.capability_taxonomy import get_default_taxonomy


class PublicationFixture:
    name = "V17CPPTool"
    capability = "language.modern_cpp"

    def __enter__(self):
        self.stack = ExitStack()
        self.tmp = Path(self.stack.enter_context(tempfile.TemporaryDirectory()))
        self.registry_path = self.tmp / "technology_registry_v1.json"
        self.real_registry = Path(production.REGISTRY_PATH)
        self.real_registry_bytes = self.real_registry.read_bytes()
        self.registry_path.write_bytes(self.real_registry_bytes)
        self.proposal_db = self.tmp / "proposals.sqlite3"
        self.review_db = self.tmp / "verification.sqlite3"
        self.stack.enter_context(patch.object(production, "REGISTRY_PATH", self.registry_path))
        self.stack.enter_context(patch.object(job_match_manager, "DB_PATH", self.tmp / "jobs.sqlite3"))
        self.stack.enter_context(patch.dict(os.environ, {"CAPABILITY_RAG_MODE": "off"}))
        self.network_guard = self.stack.enter_context(patch("socket.socket.connect", side_effect=AssertionError("Runtime network call")))
        self.embedding_guard = self.stack.enter_context(patch("tailoring.phase6d5_retrieval.retrieve_taxonomy_candidates",
                                                             side_effect=AssertionError("Runtime embedding call")))
        self.model_guard = Mock(side_effect=AssertionError("Runtime model call"))
        model = ModuleType("llm")
        model.ask_json = model.ask_text = model.completion = self.model_guard
        self.stack.enter_context(patch.dict(sys.modules, {"llm": model}))
        production.get_default_registry.cache_clear()
        rules = self.tmp / "authority.json"
        rules.write_text(json.dumps({"version": "test", "technology_domains": [
            {"technology_aliases": [self.name], "official_domains": ["fixture.example"]}
        ]}), encoding="utf-8")
        target = build_focused_verification_target({"bucket": "confirmed", "candidate_id": "v17-cpp",
            "canonical_name": self.name, "taxonomy_capabilities": [self.capability]})
        def fake(*args):
            return {"request_id": "v17-fixture-request", "results": [{"title": "Official fixture",
                "url": "https://fixture.example/docs", "content": f"{self.name} is a C++ compiler."}]}
        self.result = execute_focused_verification([target], selected_target_ids=[target["target_id"]],
            explicit_execution=True, db_path=self.review_db, api_key="fake", transport=fake)[0]["result"]
        self.interpretation = interpret_focused_verification(self.result, authority_registry_path=rules)
        self.draft = build_focused_draft(self.result, self.interpretation)
        import_proposal_bundle(self.draft["proposal_bundle"], db_path=self.proposal_db)
        self.proposal = list_proposals(db_path=self.proposal_db)[0]
        self.baseline_version = production.get_default_registry().version
        self.requirement = {"requirement_id": "v17-requirement", "text": f"Experience with {self.name}",
            "atomic_focus": f"Experience with {self.name}", "importance": "required", "score_eligible": True,
            "match_label": "none", "match_value": 0.0, "evidence_strength": 0, "evidence": []}
        return self

    def __exit__(self, *args):
        production.get_default_registry.cache_clear()
        return self.stack.__exit__(*args)

    def approve(self, decision="approve_mapping"):
        return save_proposal_review(proposal_id=self.proposal["proposal_id"],
            proposal_bundle_version=self.proposal["proposal_bundle_version"], decision=decision, db_path=self.proposal_db)

    def publish(self, **overrides):
        options = {"proposal_id": self.proposal["proposal_id"], "explicit_publish": True,
            "expected_source_fingerprint": self.proposal["source_fingerprint"],
            "expected_registry_version": self.baseline_version,
            "registry_path": self.registry_path, "db_path": self.proposal_db}
        options.update(overrides)
        return publish_approved_proposal(**options)

    def snapshots(self):
        return [{"id": 1, "discovered_job_id": 1, "taxonomy_version": get_default_taxonomy().version,
                 "stable_analysis": {"canonical_requirements": [self.requirement]}}]
