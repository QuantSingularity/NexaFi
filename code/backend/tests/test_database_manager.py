"""
Tests for DatabaseManager - fetch_one, fetch_all, execute_query
"""

import os
import sys
import tempfile
import unittest

sys.path.insert(
    0, os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)  # backend root
from shared.database.manager import (
    DatabaseManager,
    MigrationManager,
    initialize_database,
)


class TestDatabaseManager(unittest.TestCase):

    def setUp(self):
        self.db_file = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.db_file.close()
        self.db = DatabaseManager(self.db_file.name, pool_size=2)
        self.db.execute_query(
            "CREATE TABLE IF NOT EXISTS test_table (id INTEGER PRIMARY KEY, name TEXT, value INTEGER)"
        )

    def tearDown(self):
        self.db.close_all_connections()
        os.unlink(self.db_file.name)

    def test_execute_query_insert_and_select(self):
        self.db.execute_query(
            "INSERT INTO test_table (name, value) VALUES (?, ?)", ("Alice", 42)
        )
        rows = self.db.execute_query(
            "SELECT * FROM test_table WHERE name = ?", ("Alice",)
        )
        self.assertEqual(len(rows), 1)

    def test_fetch_all_returns_dicts(self):
        self.db.execute_query(
            "INSERT INTO test_table (name, value) VALUES (?, ?)", ("Bob", 10)
        )
        self.db.execute_query(
            "INSERT INTO test_table (name, value) VALUES (?, ?)", ("Carol", 20)
        )
        rows = self.db.fetch_all("SELECT * FROM test_table ORDER BY name")
        self.assertIsInstance(rows, list)
        self.assertEqual(len(rows), 2)
        self.assertIsInstance(rows[0], dict)
        self.assertEqual(rows[0]["name"], "Bob")

    def test_fetch_one_returns_dict_or_none(self):
        self.db.execute_query(
            "INSERT INTO test_table (name, value) VALUES (?, ?)", ("Dave", 99)
        )
        row = self.db.fetch_one("SELECT * FROM test_table WHERE name = ?", ("Dave",))
        self.assertIsNotNone(row)
        self.assertIsInstance(row, dict)
        self.assertEqual(row["value"], 99)

    def test_fetch_one_returns_none_when_not_found(self):
        row = self.db.fetch_one("SELECT * FROM test_table WHERE name = ?", ("Ghost",))
        self.assertIsNone(row)

    def test_fetch_all_empty_returns_empty_list(self):
        rows = self.db.fetch_all("SELECT * FROM test_table")
        self.assertEqual(rows, [])

    def test_execute_update(self):
        self.db.execute_query(
            "INSERT INTO test_table (name, value) VALUES (?, ?)", ("Eve", 5)
        )
        rowcount = self.db.execute_update(
            "UPDATE test_table SET value = ? WHERE name = ?", (50, "Eve")
        )
        self.assertEqual(rowcount, 1)
        row = self.db.fetch_one("SELECT value FROM test_table WHERE name = ?", ("Eve",))
        self.assertEqual(row["value"], 50)

    def test_execute_insert_returns_lastrowid(self):
        row_id = self.db.execute_insert(
            "INSERT INTO test_table (name, value) VALUES (?, ?)", ("Frank", 7)
        )
        self.assertIsNotNone(row_id)
        self.assertGreater(row_id, 0)

    def test_connection_pool_reuse(self):
        for i in range(5):
            self.db.execute_query(
                "INSERT INTO test_table (name, value) VALUES (?, ?)", (f"user_{i}", i)
            )
        rows = self.db.fetch_all("SELECT * FROM test_table")
        self.assertEqual(len(rows), 5)

    def test_transaction_commit(self):
        with self.db.transaction() as conn:
            conn.execute(
                "INSERT INTO test_table (name, value) VALUES (?, ?)", ("TxUser", 1)
            )
        rows = self.db.fetch_all("SELECT * FROM test_table WHERE name = ?", ("TxUser",))
        self.assertEqual(len(rows), 1)

    def test_transaction_rollback_on_error(self):
        try:
            with self.db.transaction() as conn:
                conn.execute(
                    "INSERT INTO test_table (name, value) VALUES (?, ?)",
                    ("RollUser", 1),
                )
                raise ValueError("Forced rollback")
        except ValueError:
            pass
        rows = self.db.fetch_all(
            "SELECT * FROM test_table WHERE name = ?", ("RollUser",)
        )
        self.assertEqual(len(rows), 0)


class TestMigrationManager(unittest.TestCase):

    def setUp(self):
        self.db_file = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.db_file.close()
        self.db = DatabaseManager(self.db_file.name)
        self.migration_manager = MigrationManager(self.db)

    def tearDown(self):
        self.db.close_all_connections()
        os.unlink(self.db_file.name)

    def test_apply_migration(self):
        sql = "CREATE TABLE IF NOT EXISTS migration_test (id INTEGER PRIMARY KEY, data TEXT)"
        self.migration_manager.apply_migration("001", "Test migration", sql)
        applied = self.migration_manager.get_applied_migrations()
        self.assertIn("001", applied)

    def test_apply_migration_idempotent(self):
        sql = "CREATE TABLE IF NOT EXISTS migration_test2 (id INTEGER PRIMARY KEY)"
        self.migration_manager.apply_migration("002", "Idempotent test", sql)
        self.migration_manager.apply_migration("002", "Idempotent test", sql)
        applied = self.migration_manager.get_applied_migrations()
        self.assertEqual(applied.count("002"), 1)

    def test_rollback_migration(self):
        sql = "CREATE TABLE IF NOT EXISTS rollback_test (id INTEGER PRIMARY KEY)"
        rollback_sql = "DROP TABLE IF EXISTS rollback_test"
        self.migration_manager.apply_migration("003", "Rollback test", sql)
        self.migration_manager.rollback_migration("003", rollback_sql)
        applied = self.migration_manager.get_applied_migrations()
        self.assertNotIn("003", applied)

    def test_initialize_database(self):
        db_file = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        db_file.close()
        try:
            db, mm = initialize_database(db_file.name)
            applied = mm.get_applied_migrations()
            self.assertGreater(len(applied), 0)
            db.close_all_connections()
        finally:
            os.unlink(db_file.name)


if __name__ == "__main__":
    unittest.main(verbosity=2)
