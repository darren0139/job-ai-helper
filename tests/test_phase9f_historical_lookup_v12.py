"""Regression: historical Phase 9F lookup never substitutes the active revision."""
import sqlite3
import unittest
from database.phase9f_session_revision import active_execution_row, ensure_tables


def create_schema(c):
    c.executescript("""
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
    ensure_tables(c)
    c.execute("INSERT INTO phase9f_application_confirmations VALUES ('a',1,'decision-A')")
    c.execute("INSERT INTO phase9f_confirmation_revisions VALUES ('b',1,'decision-B')")
    c.execute("INSERT INTO phase9f_active_revision VALUES (1,'b','a','phase9f-session-reconfirmation-v1')")
    c.execute("INSERT INTO phase9f_tailoring_executions VALUES ('exec-A',1,'a','gen-A','decision-A')")
    c.execute("INSERT INTO phase9f_execution_revisions VALUES ('exec-B',1,'b','gen-B','decision-B')")
    c.execute("INSERT INTO application_tailoring_generation_meta VALUES (1,'gen-A','decision-A')")
    c.execute("INSERT INTO application_tailoring_generation_meta VALUES (1,'gen-B','decision-B')")


class HistoricalLookup(unittest.TestCase):
    def setUp(self):
        self.c = sqlite3.connect(':memory:')
        self.c.row_factory = sqlite3.Row
        self.addCleanup(self.c.close)
        create_schema(self.c)

    def test_two_generations_resolve_exact_owners(self):
        self.assertEqual(active_execution_row(self.c,1)['execution_id'],'exec-B')
        self.assertEqual(active_execution_row(self.c,1,generation_id='gen-A')['execution_id'],'exec-A')
        self.assertEqual(active_execution_row(self.c,1,generation_id='gen-B')['execution_id'],'exec-B')

    def test_corrupt_original_execution_generation_fails_closed(self):
        self.c.execute("UPDATE phase9f_tailoring_executions SET generation_id='unrelated' WHERE application_id=1")
        with self.assertRaisesRegex(ValueError,'generation binding conflicts'):
            active_execution_row(self.c,1,generation_id='gen-A')

    def test_missing_execution_generation_fails_closed(self):
        self.c.execute("UPDATE phase9f_tailoring_executions SET generation_id=NULL WHERE application_id=1")
        with self.assertRaisesRegex(ValueError,'generation binding conflicts'):
            active_execution_row(self.c,1,generation_id='gen-A')

    def test_fingerprint_mismatch_fails_closed(self):
        self.c.execute("UPDATE phase9f_tailoring_executions SET phase9e_decision_fingerprint='wrong' WHERE application_id=1")
        with self.assertRaisesRegex(ValueError,'generation binding conflicts'):
            active_execution_row(self.c,1,generation_id='gen-A')

    def test_confirmation_mismatch_fails_closed(self):
        self.c.execute("UPDATE phase9f_tailoring_executions SET confirmation_id='b' WHERE application_id=1")
        with self.assertRaisesRegex(ValueError,'generation binding conflicts'):
            active_execution_row(self.c,1,generation_id='gen-A')

    def test_missing_generation_does_not_fall_back_to_current(self):
        self.assertIsNone(active_execution_row(self.c,1,generation_id='missing'))

    def test_missing_confirmed_generation_decision_fails_closed(self):
        self.c.execute("UPDATE application_tailoring_generation_meta SET phase9e_decision_fingerprint='unknown' WHERE generation_id='gen-A'")
        with self.assertRaisesRegex(ValueError,'confirmation'):
            active_execution_row(self.c,1,generation_id='gen-A')


if __name__=='__main__':
    unittest.main()
