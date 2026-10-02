"""Regression tests for complete application lifecycle deletion."""

from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from database import db_manager


class FullApplicationDeleteTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "applications.db"
        self.db_path_patcher = patch.object(db_manager, "DB_PATH", self.db_path)
        self.db_path_patcher.start()

        connection = sqlite3.connect(self.db_path)
        try:
            connection.executescript(
                """
                CREATE TABLE applications (
                    id INTEGER PRIMARY KEY,
                    session_name TEXT
                );
                CREATE TABLE application_chat_messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    application_id INTEGER NOT NULL,
                    content TEXT NOT NULL
                );
                CREATE TABLE phase9f_application_execution_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    application_id INTEGER NOT NULL,
                    event_json TEXT NOT NULL
                );
                CREATE TABLE application_provenance_links (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    application_id INTEGER NOT NULL,
                    evidence_id INTEGER NOT NULL
                );
                CREATE TABLE cross_application_edges (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source_application_id INTEGER NOT NULL,
                    target_application_id INTEGER NOT NULL
                );
                CREATE TABLE future_feature_rows (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    application_id INTEGER NOT NULL,
                    payload TEXT NOT NULL
                );
                CREATE TABLE shared_evidence (
                    id INTEGER PRIMARY KEY,
                    payload TEXT NOT NULL
                );
                CREATE TABLE global_taxonomy (
                    id INTEGER PRIMARY KEY,
                    label TEXT NOT NULL
                );
                """
            )
            connection.executemany(
                "INSERT INTO applications (id, session_name) VALUES (?, ?)",
                [(1, "delete me"), (2, "keep me")],
            )
            connection.executemany(
                "INSERT INTO application_chat_messages (application_id, content) VALUES (?, ?)",
                [(1, "a"), (2, "b")],
            )
            connection.executemany(
                "INSERT INTO phase9f_application_execution_events (application_id, event_json) VALUES (?, ?)",
                [(1, "{}"), (2, "{}")],
            )
            connection.executemany(
                "INSERT INTO application_provenance_links (application_id, evidence_id) VALUES (?, ?)",
                [(1, 100), (2, 100)],
            )
            connection.executemany(
                "INSERT INTO cross_application_edges (source_application_id, target_application_id) VALUES (?, ?)",
                [(1, 2), (2, 1), (2, 2)],
            )
            connection.executemany(
                "INSERT INTO future_feature_rows (application_id, payload) VALUES (?, ?)",
                [(1, "owned"), (2, "other")],
            )
            connection.execute(
                "INSERT INTO shared_evidence (id, payload) VALUES (100, 'shared')"
            )
            connection.execute(
                "INSERT INTO global_taxonomy (id, label) VALUES (200, 'shared taxonomy')"
            )
            connection.commit()
        finally:
            connection.close()

    def tearDown(self) -> None:
        self.db_path_patcher.stop()
        self.temp_dir.cleanup()

    def _count(self, table: str, where: str = "1=1", params: tuple = ()) -> int:
        connection = sqlite3.connect(self.db_path)
        try:
            row = connection.execute(
                f'SELECT COUNT(*) FROM "{table}" WHERE {where}',
                params,
            ).fetchone()
            return int(row[0])
        finally:
            connection.close()

    def test_delete_removes_all_application_scoped_and_link_rows(self) -> None:
        impact = db_manager.get_application_delete_impact(1)
        self.assertEqual(impact["applications"], 1)
        self.assertEqual(impact["application_chat_messages"], 1)
        self.assertEqual(impact["application_provenance_links"], 1)
        self.assertEqual(impact["future_feature_rows"], 1)
        self.assertEqual(impact["cross_application_edges"], 2)

        db_manager.delete_application_session(1)

        self.assertEqual(self._count("applications", "id = ?", (1,)), 0)
        self.assertEqual(
            self._count("application_chat_messages", "application_id = ?", (1,)), 0
        )
        self.assertEqual(
            self._count(
                "phase9f_application_execution_events",
                "application_id = ?",
                (1,),
            ),
            0,
        )
        self.assertEqual(
            self._count("application_provenance_links", "application_id = ?", (1,)), 0
        )
        self.assertEqual(
            self._count(
                "cross_application_edges",
                "source_application_id = ? OR target_application_id = ?",
                (1, 1),
            ),
            0,
        )
        self.assertEqual(
            self._count("future_feature_rows", "application_id = ?", (1,)), 0
        )

        self.assertEqual(self._count("applications", "id = ?", (2,)), 1)
        self.assertEqual(
            self._count("application_chat_messages", "application_id = ?", (2,)), 1
        )
        self.assertEqual(self._count("shared_evidence", "id = ?", (100,)), 1)
        self.assertEqual(self._count("global_taxonomy", "id = ?", (200,)), 1)
        self.assertEqual(
            self._count(
                "cross_application_edges",
                "source_application_id = 2 AND target_application_id = 2",
            ),
            1,
        )

    def test_delete_is_atomic_when_any_scoped_delete_fails(self) -> None:
        connection = sqlite3.connect(self.db_path)
        try:
            connection.executescript(
                """
                CREATE TABLE z_delete_failure (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    application_id INTEGER NOT NULL
                );
                INSERT INTO z_delete_failure (application_id) VALUES (1);
                CREATE TRIGGER fail_application_delete
                BEFORE DELETE ON z_delete_failure
                WHEN OLD.application_id = 1
                BEGIN
                    SELECT RAISE(ABORT, 'forced delete failure');
                END;
                """
            )
            connection.commit()
        finally:
            connection.close()

        with self.assertRaises(sqlite3.IntegrityError):
            db_manager.delete_application_session(1)

        self.assertEqual(self._count("applications", "id = ?", (1,)), 1)
        self.assertEqual(
            self._count("application_chat_messages", "application_id = ?", (1,)), 1
        )
        self.assertEqual(
            self._count("application_provenance_links", "application_id = ?", (1,)), 1
        )

    def test_nonexistent_application_is_deterministic_noop(self) -> None:
        before_shared = self._count("shared_evidence")
        db_manager.delete_application_session(99999)
        self.assertEqual(self._count("shared_evidence"), before_shared)

    def test_invalid_application_id_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            db_manager.delete_application_session(0)


if __name__ == "__main__":
    unittest.main()
