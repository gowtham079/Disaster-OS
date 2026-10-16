"""Tests for SEED_DEMO_USERS gating of built-in demo account seeding in init_db()."""

import os
import sqlite3
import unittest
from unittest.mock import patch

from database import _seed_default_demo_users, hash_password, should_seed_demo_users


def _memory_users_db():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute(
        """
        CREATE TABLE users (
            user_id INTEGER PRIMARY KEY,
            name VARCHAR(100) NOT NULL,
            email VARCHAR(120) UNIQUE NOT NULL,
            password VARCHAR(255) NOT NULL,
            role VARCHAR(20) DEFAULT 'operator'
        )
        """
    )
    return conn


def _demo_user_rows(conn: sqlite3.Connection):
    rows = conn.execute(
        "SELECT user_id, email FROM users WHERE email IN (?, ?) ORDER BY user_id",
        ("operator@disaster.local", "admin@disaster.local"),
    ).fetchall()
    return [dict(r) for r in rows]


class TestSeedDemoUsersFlag(unittest.TestCase):
    def test_should_seed_demo_users_unset_defaults_enabled(self):
        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("SEED_DEMO_USERS", None)
            self.assertTrue(should_seed_demo_users())

    def test_should_seed_demo_users_explicit_enabled_values(self):
        for value in ("1", "true", "TRUE", " yes ", "On"):
            with self.subTest(value=value):
                with patch.dict(os.environ, {"SEED_DEMO_USERS": value}, clear=False):
                    self.assertTrue(should_seed_demo_users())

    def test_should_seed_demo_users_explicit_disabled_values(self):
        for value in ("0", "false", "FALSE", " no ", "OFF"):
            with self.subTest(value=value):
                with patch.dict(os.environ, {"SEED_DEMO_USERS": value}, clear=False):
                    self.assertFalse(should_seed_demo_users())


class TestDemoUserSeedingBehavior(unittest.TestCase):
    def test_unset_env_seeds_demo_users(self):
        conn = _memory_users_db()
        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("SEED_DEMO_USERS", None)
            if should_seed_demo_users():
                _seed_default_demo_users(conn.cursor())
        conn.commit()
        self.assertEqual(len(_demo_user_rows(conn)), 2)
        conn.close()

    def test_enabled_env_seeds_demo_users(self):
        conn = _memory_users_db()
        with patch.dict(os.environ, {"SEED_DEMO_USERS": "true"}, clear=False):
            if should_seed_demo_users():
                _seed_default_demo_users(conn.cursor())
        conn.commit()
        self.assertEqual(len(_demo_user_rows(conn)), 2)
        conn.close()

    def test_disabled_env_does_not_seed_demo_users(self):
        conn = _memory_users_db()
        with patch.dict(os.environ, {"SEED_DEMO_USERS": "false"}, clear=False):
            if should_seed_demo_users():
                _seed_default_demo_users(conn.cursor())
        conn.commit()
        self.assertEqual(_demo_user_rows(conn), [])
        conn.close()

    def test_disabled_does_not_modify_existing_user_password(self):
        conn = _memory_users_db()
        custom_hash = hash_password("custom_operator_secret")
        conn.execute(
            "INSERT INTO users (user_id, name, email, password, role) VALUES (1, ?, ?, ?, ?)",
            ("Existing Operator", "operator@disaster.local", custom_hash, "operator"),
        )
        conn.commit()
        with patch.dict(os.environ, {"SEED_DEMO_USERS": "false"}, clear=False):
            if should_seed_demo_users():
                _seed_default_demo_users(conn.cursor())
        conn.commit()
        row = conn.execute("SELECT password FROM users WHERE user_id = 1").fetchone()
        self.assertEqual(row["password"], custom_hash)
        conn.close()


if __name__ == "__main__":
    unittest.main()
