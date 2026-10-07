"""Focused tests for the read-only production resolver inspector."""

from __future__ import annotations

import hashlib
import json
import sqlite3
import sys
import tempfile
import unittest
from contextlib import closing, contextmanager
from pathlib import Path
from types import ModuleType
from unittest.mock import Mock, patch

from database import job_match_manager
from tailoring.capability_taxonomy import TAXONOMY_PATH
from tailoring.phase6d_stable_scoring_adapter import (
    cap_requirement_with_taxonomy,
    resolve_requirement_with_production_knowledge as adapter_resolver,
)
from tailoring.production_requirement_resolver import (
    resolve_requirement_with_production_knowledge,
)
from taxonomy_discovery.production_resolver_inspector import (
    AWS_REQUIREMENT,
    WEB_SERVICES_REQUIREMENT,
    current_production_versions,
    inspect_requirement_text,
    inspect_saved_job_match,
    resolve_requirement_with_production_knowledge as inspector_resolver,
    run_production_canaries,
)
from taxonomy_discovery.production_resolver_inspector_ui import (
    render_production_resolver_inspector,
)
from taxonomy_discovery.technology_registry import REGISTRY_PATH


class _Block:
    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False


class _FakeStreamlit:
    def __init__(self, *, pressed=()):
        self.session_state = {}
        self.pressed = set(pressed)
        self.messages = []

    def tabs(self, labels):
        return [_Block() for _ in labels]

    def expander(self, _label):
        return _Block()

    def button(self, _label, *, key=None, **_kwargs):
        return key in self.pressed

    def text_area(self, _label, *, value="", **_kwargs):
        return value

    def number_input(self, _label, *, value=0, **_kwargs):
        return value

    def __getattr__(self, name):
        if name in {
            "subheader",
            "caption",
            "markdown",
            "write",
            "success",
            "warning",
            "error",
            "info",
            "json",
            "dataframe",
        }:
            return lambda *args, **kwargs: self.messages.append(
                (name, args, kwargs)
            )
        raise AttributeError(name)


class ResolverInspectorTests(unittest.TestCase):
    def test_current_versions_and_shared_production_entry_point(self):
        versions = current_production_versions()
        self.assertEqual(
            versions["taxonomy_version"],
            "phase6d-capability-taxonomy-v1.5",
        )
        self.assertEqual(
            versions["technology_registry_version"],
            "technology-registry-v1.2",
        )
        self.assertEqual(
            versions["scoring_version"],
            "stable-evidence-v1.11-phase6d17",
        )
        self.assertIs(adapter_resolver, resolve_requirement_with_production_knowledge)
        self.assertIs(inspector_resolver, resolve_requirement_with_production_knowledge)

    def test_h12_positive_and_aws_negative_expose_real_guard_diagnostics(self):
        positive = inspect_requirement_text(WEB_SERVICES_REQUIREMENT)
        self.assertEqual(positive["resolution_source"], "canonical_taxonomy")
        self.assertEqual(positive["capability_id"], "backend.api_development")
        self.assertEqual(positive["matched_phrase"], "web services")
        self.assertEqual(
            positive["matched_taxonomy_rule_type"],
            "contextual_phrase_variant",
        )
        self.assertEqual(
            positive["product_context_guard"],
            "exclude_recognized_multiword_technology_spans",
        )
        self.assertEqual(
            positive["guard_contract_version"],
            "native-product-context-guard-v1",
        )
        self.assertNotIn("match_label", positive)

        negative = inspect_requirement_text(AWS_REQUIREMENT)
        self.assertEqual(negative["resolution_source"], "unresolved")
        self.assertIsNone(negative["capability_id"])
        self.assertIn("amazon web services", negative["excluded_product_spans"])
        rejected = negative["resolver_diagnostics"]["taxonomy"][
            "rejected_candidate_rules"
        ]
        self.assertEqual(rejected[0]["phrase"], "web services")
        self.assertEqual(
            rejected[0]["reason"], "product_context_guard_excluded_phrase"
        )

    def test_cpp_react_and_all_canaries(self):
        cpp = inspect_requirement_text("C++")
        self.assertEqual(cpp["resolution_source"], "canonical_taxonomy")
        self.assertEqual(cpp["capability_id"], "language.modern_cpp")
        react = inspect_requirement_text("React")
        self.assertEqual(react["resolution_source"], "technology_registry")
        self.assertEqual(react["technology_id"], "react")
        self.assertEqual(react["capability_id"], "frontend.ui_development")
        canaries = run_production_canaries()
        self.assertTrue(canaries["all_passed"])
        self.assertEqual([row["status"] for row in canaries["rows"]], ["PASS"] * 4)

    def test_existing_scoring_adapter_uses_shared_resolution_semantics(self):
        requirement = {
            "requirement_id": "req-web",
            "text": WEB_SERVICES_REQUIREMENT,
            "atomic_focus": WEB_SERVICES_REQUIREMENT,
            "match_label": "none",
            "match_value": 0.0,
            "evidence_strength": 0,
            "evidence": [],
        }
        with patch(
            "tailoring.phase6d_stable_scoring_adapter.build_capability_retrieval_trace",
            return_value={"mode": "off"},
        ), patch(
            "tailoring.phase6d_stable_scoring_adapter.resolve_requirement_with_production_knowledge",
            wraps=resolve_requirement_with_production_knowledge,
        ) as shared:
            production = cap_requirement_with_taxonomy(
                requirement, retrieval_mode_override="off"
            )
        inspection = inspect_requirement_text(WEB_SERVICES_REQUIREMENT)
        shared.assert_called_once()
        self.assertEqual(
            production["capability_resolution_source"],
            inspection["resolution_source"],
        )
        self.assertEqual(production["capability_id"], inspection["capability_id"])

    def test_requirement_inspection_is_zero_cost_and_does_not_mutate_artifacts(self):
        taxonomy_before = TAXONOMY_PATH.read_bytes()
        registry_before = REGISTRY_PATH.read_bytes()
        fake_llm = ModuleType("llm")
        model_call = Mock(side_effect=AssertionError("model call"))
        fake_llm.ask_json = fake_llm.ask_text = fake_llm.completion = model_call
        with patch("socket.socket.connect", side_effect=AssertionError("network")), patch.dict(
            sys.modules, {"llm": fake_llm}
        ), patch(
            "taxonomy_discovery.tavily_research._default_transport",
            side_effect=AssertionError("Tavily call"),
        ), patch(
            "database.job_match_manager._connect",
            side_effect=AssertionError("database write connection"),
        ):
            inspect_requirement_text(WEB_SERVICES_REQUIREMENT)
            inspect_requirement_text(AWS_REQUIREMENT)
            run_production_canaries()
        self.assertEqual(TAXONOMY_PATH.read_bytes(), taxonomy_before)
        self.assertEqual(REGISTRY_PATH.read_bytes(), registry_before)
        model_call.assert_not_called()


class SavedSnapshotInspectorTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db = Path(self.temp.name) / "job-match.sqlite3"
        self.versions = current_production_versions()
        job_match_manager.init_job_match_schema(self.db)
        with closing(sqlite3.connect(self.db)) as connection:
            connection.execute(
                """
                CREATE TABLE discovered_jobs (
                    id INTEGER PRIMARY KEY,
                    title TEXT,
                    company TEXT,
                    content_hash TEXT,
                    lifecycle_status TEXT,
                    last_event TEXT
                )
                """
            )
            connection.execute(
                "INSERT INTO discovered_jobs VALUES (566,?,?,?,?,?)",
                ("Backend Engineer", "Example", "job-hash", "active", "unchanged"),
            )
            connection.execute(
                "CREATE TABLE governed_research_results (result_id TEXT PRIMARY KEY)"
            )
            connection.execute(
                "CREATE TABLE governed_publications (publication_id TEXT PRIMARY KEY)"
            )
            connection.commit()
        self.requirements = [
            {
                "requirement_id": "req-web",
                "text": WEB_SERVICES_REQUIREMENT,
                "importance": "required",
                "capability_resolution_source": "canonical_taxonomy",
                "capability_id": "backend.api_development",
                "technology_registry_technology_id": None,
                "resolution_status": None,
                "match_label": "direct",
                "evidence_strength": 5,
                "evidence": [{"evidence_id": "ev-1", "text": "Built REST APIs"}],
            },
            {
                "requirement_id": "req-aws",
                "text": AWS_REQUIREMENT,
                "importance": "required",
                "capability_resolution_source": "unresolved",
                "capability_id": None,
                "technology_registry_technology_id": None,
                "resolution_status": None,
                "match_label": "none",
                "evidence_strength": 0,
                "evidence": [],
            },
        ]
        job_match_manager.save_job_match_snapshot(
            discovered_job_id=566,
            job_content_hash="job-hash",
            evidence_fingerprint="evidence-fingerprint",
            match_version=self.versions["match_version"],
            scoring_version=self.versions["scoring_version"],
            taxonomy_version=self.versions["taxonomy_version"],
            jd_profile={"required_skills": [WEB_SERVICES_REQUIREMENT, AWS_REQUIREMENT]},
            evidence_snapshot=[],
            stable_analysis={
                "technology_registry_version": self.versions[
                    "technology_registry_version"
                ],
                "canonical_requirements": self.requirements,
                "model_call_count": 0,
                "network_call_count": 0,
            },
            summary={},
            db_path=self.db,
        )
        with closing(sqlite3.connect(self.db)) as connection:
            connection.execute("UPDATE job_match_snapshots SET id=43")
            connection.commit()

    def tearDown(self):
        self.temp.cleanup()

    def _database_state(self):
        data = self.db.read_bytes()
        with closing(sqlite3.connect(self.db)) as connection:
            tables = connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
            ).fetchall()
            counts = {
                name: connection.execute(f'SELECT COUNT(*) FROM "{name}"').fetchone()[0]
                for (name,) in tables
                if not name.startswith("sqlite_")
            }
        return hashlib.sha256(data).hexdigest(), self.db.stat().st_mtime_ns, counts

    def test_saved_job_match_is_loaded_faithfully_without_recompute_or_write(self):
        before = self._database_state()
        with patch(
            "job_discovery.matching.analyze_job_match",
            side_effect=AssertionError("must not rebuild Job Match"),
        ), patch(
            "job_discovery.matching._default_stable_builder",
            side_effect=AssertionError("must not recompute Job Match"),
        ):
            result = inspect_saved_job_match(566, db_path=self.db)
        after = self._database_state()
        self.assertEqual(before, after)
        self.assertEqual(result["status"], "found")
        self.assertEqual(result["snapshot_metadata"]["snapshot_id"], 43)
        self.assertEqual(
            result["snapshot_metadata"]["currentness_status"],
            "latest_saved_current_versions",
        )
        rows = result["requirement_rows"]
        self.assertEqual(rows[0]["resolution_source"], "canonical_taxonomy")
        self.assertEqual(rows[0]["capability_id"], "backend.api_development")
        self.assertEqual(rows[0]["match_label"], "direct")
        self.assertIsNone(rows[0]["resolution_status"])
        self.assertEqual(rows[1]["resolution_source"], "unresolved")
        self.assertIsNone(rows[1]["capability_id"])
        self.assertEqual(rows[1]["match_label"], "none")
        self.assertEqual(
            result["persisted_requirements"], self.requirements
        )
        self.assertEqual(
            result["persisted_execution_metadata"][
                "stable_analysis.model_call_count"
            ],
            0,
        )

    def test_historical_versions_and_missing_ids_fail_closed(self):
        with closing(sqlite3.connect(self.db)) as connection:
            connection.execute(
                "UPDATE job_match_snapshots SET taxonomy_version='historical-taxonomy'"
            )
            connection.commit()
        historical = inspect_saved_job_match(566, db_path=self.db)
        self.assertEqual(
            historical["snapshot_metadata"]["currentness_status"],
            "historical_or_stale",
        )
        self.assertIn(
            "taxonomy version differs",
            historical["snapshot_metadata"]["stale_reasons"],
        )
        self.assertEqual(
            historical["persisted_requirements"], self.requirements
        )
        missing = inspect_saved_job_match(999, db_path=self.db)
        self.assertEqual(missing["status"], "not_found")
        with self.assertRaises(ValueError):
            inspect_saved_job_match(0, db_path=self.db)


class StreamlitInspectorTests(unittest.TestCase):
    @contextmanager
    def _streamlit(self, fake):
        with patch.dict(sys.modules, {"streamlit": fake}):
            yield

    def test_passive_render_has_no_inspection_side_effects(self):
        fake = _FakeStreamlit()
        requirement = Mock(side_effect=AssertionError("implicit requirement run"))
        snapshot = Mock(side_effect=AssertionError("implicit snapshot read"))
        canaries = Mock(side_effect=AssertionError("implicit canary run"))
        with self._streamlit(fake):
            render_production_resolver_inspector(
                version_loader=lambda: {
                    "taxonomy_version": "taxonomy",
                    "technology_registry_version": "registry",
                    "scoring_version": "scorer",
                },
                requirement_inspector=requirement,
                snapshot_inspector=snapshot,
                canary_runner=canaries,
            )
        requirement.assert_not_called()
        snapshot.assert_not_called()
        canaries.assert_not_called()

    def test_only_explicitly_pressed_action_executes(self):
        fake = _FakeStreamlit(pressed={"tqd3_production_resolver_inspect"})
        requirement = Mock(
            return_value={
                "resolution_source": "unresolved",
                "resolver_diagnostics": {},
            }
        )
        snapshot = Mock(side_effect=AssertionError("snapshot read"))
        canaries = Mock(side_effect=AssertionError("canary run"))
        with self._streamlit(fake):
            render_production_resolver_inspector(
                version_loader=lambda: {
                    "taxonomy_version": "taxonomy",
                    "technology_registry_version": "registry",
                    "scoring_version": "scorer",
                },
                requirement_inspector=requirement,
                snapshot_inspector=snapshot,
                canary_runner=canaries,
            )
        requirement.assert_called_once_with(WEB_SERVICES_REQUIREMENT)
        snapshot.assert_not_called()
        canaries.assert_not_called()


if __name__ == "__main__":
    unittest.main()
