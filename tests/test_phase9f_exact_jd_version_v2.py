"""Regression for NCS PRE-D normalized-ID collision (synthetic text pair)."""
from contextlib import closing
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from database import jd_library_manager as manager
from rag.jd_identity import exact_source_version_id, source_version_id, source_version_matches

OLD = ('Responsibilities\nBuild Python APIs and maintain reliable software services.\n'
       'Requirements\nPython, REST APIs and automated tests.\n'
       'Collaborate with stakeholders on software delivery.')
NEW = OLD.replace('Build Python APIs', 'BUILD  Python APIs')
PROFILE = {'job_title': 'AI Software Engineer', 'company': 'NCS', 'location': 'Singapore',
           'responsibilities': ['Build Python APIs and maintain reliable software services.'],
           'required_skills': ['Python', 'REST APIs'], 'preferred_skills': [],
           'tools_technologies': ['Python'], 'soft_skills': [], 'buzzwords': [], 'deal_breakers': []}
PROFILE_NEW = {**PROFILE, 'buzzwords': ['Reliable software delivery']}


class ExactJDStorageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.old_db = manager.DB_PATH
        self.addCleanup(setattr, manager, 'DB_PATH', self.old_db)
        manager.DB_PATH = Path(self.temp.name) / 'isolated.sqlite'
        manager.init_jd_library()

    def seed_legacy(self):
        saved = manager.save_job_description_to_library(raw_text=OLD, jd_profile=PROFILE)
        manager.save_or_link_job_description_for_application(application_id=91, raw_text=OLD, jd_profile=PROFILE)
        job_id = saved['job_description_id']
        legacy_id = source_version_id(OLD)
        with closing(manager._connect()) as c, c:
            for table, key in [('job_descriptions', 'id'), ('job_description_versions', 'job_description_id'),
                               ('application_job_links', 'job_description_id')]:
                c.execute(f'UPDATE {table} SET source_version_id=? WHERE {key}=?', (legacy_id, job_id))
        return job_id, legacy_id

    def test_first_version_table_migration_preserves_existing_legacy_link(self):
        # Phase 9D/9E fixtures have a canonical row and a link table but no
        # version table yet. The pre-migration link already owns its ID.
        job_id, legacy_id = self.seed_legacy()
        with closing(manager._connect()) as c, c:
            links_before = manager.get_application_job_links()
            c.execute("DROP TABLE job_description_versions")
            c.execute("DROP TABLE job_description_version_availability")
        manager.init_jd_library()
        self.assertEqual(manager.get_application_job_links(), links_before)
        self.assertEqual(manager.get_job_description_by_id(job_id)['source_version_id'], legacy_id)
        versions = manager.get_job_description_versions(job_id)
        self.assertEqual(len(versions), 1)
        self.assertEqual(versions[0]['source_version_id'], legacy_id)
        self.assertEqual(versions[0]['raw_text'], OLD)
        self.assertEqual(versions[0]['jd_profile'], PROFILE)
        # Use the same relational join as Phase 9E context validation.
        with closing(manager._connect()) as c:
            row = c.execute("""SELECT version.raw_text, version.jd_profile_json
                FROM application_job_links AS link
                JOIN job_descriptions AS job ON job.id = link.job_description_id
                JOIN job_description_versions AS version
                  ON version.job_description_id = link.job_description_id
                 AND version.source_version_id = link.source_version_id
                WHERE link.application_id = ?""", (91,)).fetchone()
        self.assertIsNotNone(row)
        self.assertEqual(row['raw_text'], OLD)
        self.assertEqual(json.loads(row['jd_profile_json']), PROFILE)
        manager.init_jd_library()
        self.assertEqual(manager.get_job_description_versions(job_id), versions)
        self.assertEqual(manager.get_application_job_links(), links_before)
        new = manager.save_job_description_to_library(raw_text=NEW, jd_profile=PROFILE_NEW)
        self.assertEqual(new['source_version_id'], exact_source_version_id(NEW))
        manager.init_jd_library()
        self.assertEqual(manager.get_application_job_links(), links_before)
        self.assertEqual(len(manager.get_job_description_versions(job_id)), 2)

    def test_missing_historical_version_in_existing_table_is_not_guessed(self):
        job_id, legacy_id = self.seed_legacy()
        with closing(manager._connect()) as c, c:
            c.execute("DELETE FROM job_description_versions WHERE job_description_id=?", (job_id,))
        links_before = manager.get_application_job_links()
        manager.init_jd_library()
        self.assertEqual(manager.get_application_job_links(), links_before)
        self.assertEqual(manager.get_job_description_by_id(job_id)['source_version_id'], exact_source_version_id(OLD))
        self.assertNotIn(legacy_id, {v['source_version_id'] for v in manager.get_job_description_versions(job_id)})

    def test_legacy_collision_creates_new_version_and_restart_preserves_both(self):
        self.assertEqual(source_version_id(OLD), source_version_id(NEW))
        self.assertNotEqual(exact_source_version_id(OLD), exact_source_version_id(NEW))
        job_id, legacy_id = self.seed_legacy()
        second = manager.save_job_description_to_library(raw_text=NEW, jd_profile=PROFILE_NEW)
        self.assertEqual(second['job_description_id'], job_id)
        self.assertTrue(second['created_new_version'])
        self.assertEqual(second['source_version_id'], exact_source_version_id(NEW))
        self.assertFalse(source_version_matches(OLD, second['source_version_id']))
        self.assertTrue(source_version_matches(OLD, legacy_id))
        before = manager.get_job_description_versions(job_id)
        manager.init_jd_library()
        self.assertEqual(before, manager.get_job_description_versions(job_id))
        self.assertEqual(manager.get_job_description_by_id(job_id)['source_version_id'], second['source_version_id'])
        self.assertEqual(manager.get_application_job_links()[0]['source_version_id'], legacy_id)
        by_id = {x['source_version_id']: x for x in before}
        self.assertEqual(by_id[legacy_id]['raw_text'], OLD)
        self.assertEqual(by_id[legacy_id]['jd_profile'], PROFILE)
        self.assertEqual(by_id[second['source_version_id']]['jd_profile'], PROFILE_NEW)
        for text, version in [(OLD, legacy_id), (NEW, second['source_version_id'])]:
            repeat = manager.save_job_description_to_library(raw_text=text, jd_profile=PROFILE)
            self.assertEqual(repeat['source_version_id'], version)
            self.assertFalse(repeat['created_new_version'])
            self.assertFalse(repeat['needs_chroma_index'])
        self.assertEqual(manager.get_jd_library_stats(), {'canonical_jobs': 1, 'versions': 2, 'session_links': 1})

    def test_application_save_collision_and_legacy_link(self):
        job_id, legacy_id = self.seed_legacy()
        saved = manager.save_or_link_job_description_for_application(application_id=92, raw_text=NEW, jd_profile=PROFILE_NEW)
        self.assertEqual(saved['job_description_id'], job_id)
        self.assertTrue(saved['created_new_version'])
        links = {r['application_id']: r['source_version_id'] for r in manager.get_application_job_links()}
        self.assertEqual(links, {91: legacy_id, 92: exact_source_version_id(NEW)})

    def test_exact_lookup_legacy_and_new_and_ambiguous_identity(self):
        job_id, legacy_id = self.seed_legacy()
        with patch.object(manager, 'get_exact_job_description_version', side_effect=lambda j, v: (j, v)):
            self.assertEqual(manager.find_exact_saved_jd_by_raw_text(OLD), (job_id, legacy_id))
            self.assertIsNone(manager.find_exact_saved_jd_by_raw_text(NEW))
            new = manager.save_job_description_to_library(raw_text=NEW, jd_profile=PROFILE_NEW)
            self.assertEqual(manager.find_exact_saved_jd_by_raw_text(NEW), (job_id, new['source_version_id']))
            manager.save_job_description_to_library(raw_text=NEW, jd_profile={**PROFILE_NEW, 'company': 'Other'})
            self.assertIsNone(manager.find_exact_saved_jd_by_raw_text(NEW))
            self.assertEqual(manager.find_exact_saved_jd_by_raw_text(NEW, company='NCS'), (job_id, new['source_version_id']))
            self.assertIsNone(manager.find_exact_saved_jd_by_raw_text(NEW, company='Unrelated'))

    def test_raw_collision_cannot_overwrite_existing_id(self):
        job_id, legacy_id = self.seed_legacy()
        with closing(manager._connect()) as c, c:
            with self.assertRaisesRegex(ValueError, 'collision'):
                manager._upsert_version(c.cursor(), job_description_id=job_id, source_version_id=legacy_id,
                                        raw_text=NEW, jd_profile_json='{}', created_at='now')
        self.assertEqual(manager.get_job_description_versions(job_id)[0]['raw_text'], OLD)

    def test_exact_identity_uses_original_utf8(self):
        self.assertEqual(exact_source_version_id(NEW), 'jdv_exact_' + hashlib.sha256(NEW.encode('utf-8')).hexdigest())
        self.assertFalse(source_version_matches(NEW, 'jdv_exact_' + '0'*64))


class ExactJDNativeWorkflowTests(unittest.TestCase):
    setUp = ExactJDStorageTests.setUp
    seed_legacy = ExactJDStorageTests.seed_legacy
    # Native integration intentionally uses the actual canonicalizer, intake,
    # ranking validation and PRE-D bridge. No API or Chroma call is made.
    def test_native_pre_d_collision_and_zero_cost_repeat(self):
        from tailoring.phase9f_jd_intake import build_transient_exact_jd_snapshot, build_reused_exact_jd_snapshot
        from tailoring.phase9f_application_confirmation_ui import prepare_persisted_exact_jd_for_confirmation
        from tailoring.phase9f_starting_source_ranking import validate_exact_jd_snapshot
        job_id, legacy_id = self.seed_legacy()
        analyzed = build_transient_exact_jd_snapshot(raw_text=NEW, jd_profile=deepcopy(PROFILE_NEW), source_type='pasted')
        validate_exact_jd_snapshot(analyzed)
        indexed = []
        persisted, receipt = prepare_persisted_exact_jd_for_confirmation(analyzed, index_fn=lambda j: indexed.append(j) or 1)
        validate_exact_jd_snapshot(persisted)
        self.assertTrue(receipt['created_new_version'])
        self.assertEqual(persisted['raw_jd_sha256'], analyzed['raw_jd_sha256'])
        self.assertEqual(persisted['jd_profile'], analyzed['jd_profile'])
        self.assertEqual(persisted['canonical_requirement_fingerprint'], analyzed['canonical_requirement_fingerprint'])
        self.assertEqual(persisted['source_version_id'], analyzed['source_version_id'])
        old = manager.get_exact_job_description_for_application(91)
        self.assertEqual(old['raw_text'], OLD)
        exact = manager.find_exact_saved_jd_by_raw_text(NEW)
        reused = build_reused_exact_jd_snapshot(exact, source_type='pasted')
        self.assertEqual(reused['model_call_count'], 0)
        self.assertEqual(reused['jd_profile'], analyzed['jd_profile'])
        _, repeat = prepare_persisted_exact_jd_for_confirmation(reused, index_fn=lambda j: indexed.append(j) or 1)
        self.assertTrue(repeat['exact_existing_version_reused'])
        self.assertEqual(indexed, [job_id])
        self.assertEqual(old['source_version_id'], legacy_id)
