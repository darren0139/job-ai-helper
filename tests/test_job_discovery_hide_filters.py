from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from database import job_discovery_manager as manager
from job_discovery.hide_filters import (
    job_identity,
    partition_hidden_jobs,
    rule_matches_job,
)


class HideFilterPureTests(unittest.TestCase):
    def _job(self, **overrides):
        job = {
            "source": "smartrecruiters",
            "source_job_id": "NCS3:123",
            "title": "Senior Software Engineer",
            "company": "NCS",
            "description": "Build Java and Python services.",
            "seniority": "Senior",
            "employment_type": "Full-time",
            "experience_years_min": 5,
        }
        job.update(overrides)
        return job

    def test_individual_job_rule(self):
        job = self._job()
        rule = {"rule_type": "job", "value": job_identity(job), "enabled": True}
        self.assertTrue(rule_matches_job(job, rule))

    def test_company_rule_is_exact_not_substring(self):
        rule = {"rule_type": "company", "value": "NCS", "enabled": True}
        self.assertTrue(rule_matches_job(self._job(company="NCS"), rule))
        self.assertFalse(rule_matches_job(self._job(company="NCS Group"), rule))

    def test_title_keyword_is_case_insensitive(self):
        rule = {"rule_type": "title_keyword", "value": "SENIOR", "enabled": True}
        self.assertTrue(rule_matches_job(self._job(), rule))

    def test_description_keyword(self):
        rule = {"rule_type": "description_keyword", "value": "python", "enabled": True}
        self.assertTrue(rule_matches_job(self._job(), rule))

    def test_experience_rule_uses_explicit_minimum_only(self):
        rule = {"rule_type": "experience_min_above", "value": "3", "enabled": True}
        self.assertTrue(rule_matches_job(self._job(experience_years_min=5), rule))
        self.assertFalse(rule_matches_job(self._job(experience_years_min=2), rule))
        self.assertFalse(rule_matches_job(self._job(experience_years_min=None), rule))

    def test_disabled_rule_is_ignored(self):
        rule = {"rule_type": "title_keyword", "value": "senior", "enabled": False}
        self.assertFalse(rule_matches_job(self._job(), rule))

    def test_partition_preserves_hidden_reason(self):
        rules = [{"rule_type": "title_keyword", "value": "senior", "enabled": True}]
        visible, hidden = partition_hidden_jobs(
            [self._job(source_job_id="1"), self._job(source_job_id="2", title="Junior Engineer")],
            rules,
        )
        self.assertEqual(len(visible), 1)
        self.assertEqual(len(hidden), 1)
        self.assertTrue(hidden[0]["_hide_reasons"])


class HideFilterPersistenceTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tempdir.cleanup)
        self.db_path = Path(self.tempdir.name) / "applications.db"
        patcher = patch.object(manager, "DB_PATH", self.db_path)
        patcher.start()
        self.addCleanup(patcher.stop)
        manager.init_job_discovery_schema()

    def test_rule_create_disable_reenable_and_delete(self):
        rule_id = manager.upsert_hide_rule(
            rule_type="title_keyword",
            value="Senior",
        )
        rules = manager.list_hide_rules(include_disabled=True)
        self.assertEqual(len(rules), 1)
        self.assertTrue(rules[0]["enabled"])
        self.assertEqual(rules[0]["normalized_value"], "senior")

        manager.set_hide_rule_enabled(rule_id, False)
        self.assertEqual(manager.list_hide_rules(include_disabled=False), [])

        same_id = manager.upsert_hide_rule(
            rule_type="title_keyword",
            value=" senior ",
        )
        self.assertEqual(same_id, rule_id)
        self.assertTrue(manager.list_hide_rules(include_disabled=False)[0]["enabled"])

        manager.delete_hide_rule(rule_id)
        self.assertEqual(manager.list_hide_rules(include_disabled=True), [])

    def test_experience_rule_is_normalized_numerically(self):
        rule_id = manager.upsert_hide_rule(
            rule_type="experience_min_above",
            value="3.0",
        )
        rule = manager.list_hide_rules(include_disabled=True)[0]
        self.assertEqual(rule["id"], rule_id)
        self.assertEqual(rule["normalized_value"], "3")


if __name__ == "__main__":
    unittest.main()
