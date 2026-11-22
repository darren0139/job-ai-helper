"""Isolated, disposable approval identity and revision ownership tests.

This module deliberately does not import the full app or use a live database.
"""
from __future__ import annotations

from contextlib import closing

import ast
import sqlite3
import tempfile
import unittest
from pathlib import Path
from typing import Any

from database.phase9f_session_revision import (
    active_execution_row,
    ensure_tables,
    phase9f_application_owns_generation,
)

ROOT = Path(__file__).resolve().parents[1]


def create_schema(connection):
    connection.executescript("""
    CREATE TABLE phase9f_application_confirmations (
        confirmation_id TEXT PRIMARY KEY, application_id INTEGER NOT NULL UNIQUE,
        phase9e_decision_fingerprint TEXT NOT NULL);
    CREATE TABLE phase9f_tailoring_executions (
        execution_id TEXT PRIMARY KEY, application_id INTEGER NOT NULL UNIQUE,
        confirmation_id TEXT NOT NULL, generation_id TEXT,
        phase9e_decision_fingerprint TEXT);
    CREATE TABLE application_tailoring_generation_meta (
        application_id INTEGER NOT NULL, generation_id TEXT,
        phase9e_decision_fingerprint TEXT);
    """)
    ensure_tables(connection)


def approval_function():
    """Load the *actual* production approval function without app dependencies."""
    path = ROOT / "database" / "tailoring_generation_control.py"
    tree = ast.parse(path.read_text(encoding="utf-8-sig"))
    fn = next(node for node in tree.body if isinstance(node, ast.FunctionDef)
              and node.name == "approve_tailoring_generation")
    code = compile(ast.Module(body=[fn], type_ignores=[]), str(path), "exec")
    namespace = {"Any": Any}
    exec(code, namespace)
    return namespace[fn.name], namespace


class ApprovalRevisionIntegrity(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.db = Path(self.tmp.name) / "only_disposable.sqlite"
        with closing(self.connect()) as c, c:
            create_schema(c)
            c.execute("INSERT INTO phase9f_application_confirmations VALUES ('a',1,'decision-A')")
            c.execute("INSERT INTO phase9f_confirmation_revisions VALUES ('b',1,'decision-B')")
            c.execute("INSERT INTO phase9f_active_revision VALUES (1,'b','a','phase9f-session-reconfirmation-v1')")
            c.execute("INSERT INTO phase9f_tailoring_executions VALUES ('exec-A',1,'a','gen-A','decision-A')")
            c.execute("INSERT INTO phase9f_execution_revisions VALUES ('exec-B',1,'b','gen-B','decision-B')")
            c.execute("INSERT INTO application_tailoring_generation_meta VALUES (1,'gen-A','decision-A')")
            c.execute("INSERT INTO application_tailoring_generation_meta VALUES (1,'gen-B','decision-B')")

    def connect(self):
        c = sqlite3.connect(self.db)
        c.row_factory = sqlite3.Row
        return c

    def test_original_and_revision_have_independent_ownership(self):
        with closing(self.connect()) as c, c:
            self.assertTrue(phase9f_application_owns_generation(c,1,'decision-A'))
            self.assertTrue(phase9f_application_owns_generation(c,1,'decision-B'))
            self.assertEqual(active_execution_row(c,1,generation_id='gen-A')['execution_id'],'exec-A')
            self.assertEqual(active_execution_row(c,1,generation_id='gen-B')['execution_id'],'exec-B')
            self.assertEqual(active_execution_row(c,1)['execution_id'],'exec-B')

    def test_unknown_or_missing_binding_fails_closed(self):
        with closing(self.connect()) as c, c:
            for fp in ('', 'legacy-phase9e', 'decision-other-application'):
                with self.subTest(fp=fp), self.assertRaisesRegex(ValueError,'legacy approval is forbidden'):
                    phase9f_application_owns_generation(c,1,fp)

    def test_historical_execution_must_match_exact_generation(self):
        with closing(self.connect()) as c, c:
            c.execute("UPDATE phase9f_tailoring_executions SET generation_id='gen-X' WHERE application_id=1")
            with self.assertRaisesRegex(ValueError, 'generation binding conflicts'):
                active_execution_row(c,1,generation_id='gen-A')
            c.execute("UPDATE phase9f_tailoring_executions SET generation_id=NULL WHERE application_id=1")
            with self.assertRaisesRegex(ValueError, 'generation binding conflicts'):
                active_execution_row(c,1,generation_id='gen-A')

    def test_dangling_active_revision_cannot_be_treated_as_legacy(self):
        with closing(self.connect()) as c, c:
            c.execute("DELETE FROM phase9f_application_confirmations WHERE application_id=1")
            c.execute("DELETE FROM phase9f_confirmation_revisions WHERE application_id=1")
            with self.assertRaisesRegex(ValueError, 'legacy approval is forbidden'):
                phase9f_application_owns_generation(c,1,'decision-B')

    def test_genuinely_legacy_application_remains_legacy(self):
        with closing(self.connect()) as c, c:
            self.assertFalse(phase9f_application_owns_generation(c,2,'legacy-decision'))
            self.assertFalse(phase9f_application_owns_generation(c,2,''))

    def test_revision_tables_are_additive_not_unique_by_application(self):
        with closing(self.connect()) as c, c:
            c.execute("INSERT INTO phase9f_confirmation_revisions VALUES ('c',1,'decision-C')")
            c.execute("INSERT INTO phase9f_execution_revisions VALUES ('exec-C',1,'c','gen-C','decision-C')")
            self.assertEqual(c.execute('SELECT COUNT(*) FROM phase9f_confirmation_revisions WHERE application_id=1').fetchone()[0],2)

    def test_actual_direct_approval_rejects_legacy_downgrade_before_write(self):
        approve, ns = approval_function()
        class ReachedWrite(Exception): pass
        ns.update({
            'PHASE9F_F_NORMAL_LIFECYCLE_VERSION':'phase9f-f-normal-generation-lifecycle-v1',
            'get_tailoring_generation':lambda app,gen: ns['current'],
            'get_phase9f_normal_generation_lifecycle':lambda gen: gen.get('generation_settings',{}).get('phase9f_f_normal_lifecycle',{}),
            'is_phase9f_normal_generation_approvable':lambda gen: True,
            '_connect': self.connect,
            'record_generation_metadata':lambda **kw: (_ for _ in ()).throw(ReachedWrite()),
        })
        for decision in ('decision-B','legacy-phase9e',''):
            with self.subTest(decision=decision):
                ns['current']={'phase9e_decision_fingerprint':decision,'generation_kind':'legacy'}
                with self.assertRaisesRegex(ValueError,'legacy approval is forbidden'):
                    approve(1,'gen-B')
        ns['current']={'phase9e_decision_fingerprint':'legacy-phase9e','generation_kind':'legacy'}
        with self.assertRaises(ReachedWrite):
            approve(2,'gen-legacy')

    def test_valid_confirmation_without_matching_execution_cannot_approve(self):
        approve, ns = approval_function()
        ns.update({
            'PHASE9F_F_NORMAL_LIFECYCLE_VERSION':'phase9f-f-normal-generation-lifecycle-v1',
            'get_tailoring_generation':lambda app,gen: {
                'phase9e_decision_fingerprint':'decision-B',
                'generation_kind':'phase9f_f_tailoring',
                'generation_settings':{'phase9f_f_normal_lifecycle':{
                    'lifecycle_version':'phase9f-f-normal-generation-lifecycle-v1',
                    'generation_status':'completed',
                }},
            },
            'get_phase9f_normal_generation_lifecycle':lambda gen:gen['generation_settings']['phase9f_f_normal_lifecycle'],
            'is_phase9f_normal_generation_approvable':lambda gen:True,
            '_connect': self.connect,
            'record_generation_metadata':lambda **kw:self.fail('Approval write was reached'),
        })
        with self.assertRaisesRegex(ValueError,'execution bound to this exact frozen generation'):
            approve(1,'gen-not-owned')

    def test_legacy_binding_rechecks_under_write_lock(self):
        p = ROOT/'database'/'application_blueprint_manager.py'
        src=p.read_text(encoding='utf-8-sig')
        body=src[src.index('def evaluate_and_bind_application_blueprint('):]
        begin=body.index('connection.execute("BEGIN IMMEDIATE")')
        signature=body.index('after_signature = _database_context_signature')
        self.assertIn('phase9f_active_revision',body[begin:signature])
        self.assertIn('phase9f_application_confirmations',body[begin:signature])


if __name__=='__main__':
    unittest.main()
