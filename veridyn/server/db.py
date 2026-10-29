"""In-memory and persistent session, challenge, and attempt storage.

TOC Concept: Ephemeral State Storage for Inductive Verification Sessions and Transactional Audit Logs.
"""

from __future__ import annotations

import json
import sqlite3
import threading
from typing import Any

from veridyn.server.session import SessionState, current_timestamp, generate_session_id


class Database:
    """Thread-safe SQLite database manager for VeriDyn sessions and challenges."""

    def __init__(self, db_path: str = ":memory:") -> None:
        self.db_path = db_path
        self._lock = threading.Lock()
        # For in-memory database, maintain a persistent connection so tables persist across operations
        self._conn = sqlite3.connect(
            db_path,
            check_same_thread=False,
            autocommit=False,
        )
        self._conn.row_factory = sqlite3.Row
        self.init_db()

    def init_db(self) -> None:
        """Create tables with parameterized schemas if they do not exist."""
        with self._lock:
            cur = self._conn.cursor()
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS sessions (
                    session_id TEXT PRIMARY KEY,
                    level INTEGER NOT NULL,
                    attempts_left INTEGER NOT NULL,
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL
                );
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS challenges (
                    nonce TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    level INTEGER NOT NULL,
                    rule_name TEXT NOT NULL,
                    regex_str TEXT NOT NULL,
                    dfa_signature TEXT NOT NULL,
                    positive_examples TEXT NOT NULL,
                    negative_examples TEXT NOT NULL,
                    test_strings TEXT NOT NULL,
                    correct_labels TEXT NOT NULL,
                    certificate_data TEXT NOT NULL,
                    expires_at REAL NOT NULL,
                    created_at REAL NOT NULL,
                    used INTEGER NOT NULL DEFAULT 0,
                    FOREIGN KEY(session_id) REFERENCES sessions(session_id)
                );
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS attempts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    nonce TEXT NOT NULL,
                    ip_address TEXT,
                    answers TEXT NOT NULL,
                    correct_count INTEGER NOT NULL,
                    total_tests INTEGER NOT NULL,
                    passed INTEGER NOT NULL,
                    error_code TEXT,
                    created_at REAL NOT NULL,
                    FOREIGN KEY(session_id) REFERENCES sessions(session_id)
                );
                """
            )
            self._conn.commit()

    def get_or_create_session(
        self,
        session_id: str | None,
        level: int,
        max_attempts: int = 3,
    ) -> SessionState:
        """Fetch existing session or initialize a new one with given attempts."""
        now = current_timestamp()
        with self._lock:
            cur = self._conn.cursor()
            if session_id:
                cur.execute(
                    "SELECT session_id, level, attempts_left, created_at, updated_at FROM sessions WHERE session_id = ?",
                    (session_id,),
                )
                row = cur.fetchone()
                if row:
                    return SessionState(
                        session_id=row["session_id"],
                        level=row["level"],
                        attempts_left=row["attempts_left"],
                        created_at=row["created_at"],
                        updated_at=row["updated_at"],
                    )

            # Create fresh session
            new_id = generate_session_id() if not session_id else session_id
            cur.execute(
                """
                INSERT INTO sessions (session_id, level, attempts_left, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (new_id, level, max_attempts, now, now),
            )
            self._conn.commit()
            return SessionState(
                session_id=new_id,
                level=level,
                attempts_left=max_attempts,
                created_at=now,
                updated_at=now,
            )

    def get_session(self, session_id: str) -> SessionState | None:
        """Fetch session metadata by ID."""
        with self._lock:
            cur = self._conn.cursor()
            cur.execute(
                "SELECT session_id, level, attempts_left, created_at, updated_at FROM sessions WHERE session_id = ?",
                (session_id,),
            )
            row = cur.fetchone()
            if not row:
                return None
            return SessionState(
                session_id=row["session_id"],
                level=row["level"],
                attempts_left=row["attempts_left"],
                created_at=row["created_at"],
                updated_at=row["updated_at"],
            )

    def decrement_session_attempts(self, session_id: str) -> int:
        """Decrement attempts_left for a session and return remaining count."""
        now = current_timestamp()
        with self._lock:
            cur = self._conn.cursor()
            cur.execute(
                """
                UPDATE sessions
                SET attempts_left = MAX(0, attempts_left - 1), updated_at = ?
                WHERE session_id = ?
                """,
                (now, session_id),
            )
            cur.execute(
                "SELECT attempts_left FROM sessions WHERE session_id = ?",
                (session_id,),
            )
            row = cur.fetchone()
            self._conn.commit()
            return row["attempts_left"] if row else 0

    def store_challenge(
        self,
        nonce: str,
        session_id: str,
        level: int,
        rule_name: str,
        regex_str: str,
        dfa_signature: str,
        positive_examples: list[str],
        negative_examples: list[str],
        test_strings: list[dict[str, str]],
        correct_labels: dict[str, str],
        certificate_data: dict[str, Any],
        expires_at: float,
    ) -> None:
        """Store challenge secrets and public artifacts with parameter binding."""
        now = current_timestamp()
        with self._lock:
            cur = self._conn.cursor()
            cur.execute(
                """
                INSERT INTO challenges (
                    nonce, session_id, level, rule_name, regex_str, dfa_signature,
                    positive_examples, negative_examples, test_strings,
                    correct_labels, certificate_data, expires_at, created_at, used
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
                """,
                (
                    nonce,
                    session_id,
                    level,
                    rule_name,
                    regex_str,
                    dfa_signature,
                    json.dumps(positive_examples),
                    json.dumps(negative_examples),
                    json.dumps(test_strings),
                    json.dumps(correct_labels),
                    json.dumps(certificate_data),
                    expires_at,
                    now,
                ),
            )
            self._conn.commit()

    def get_challenge(self, nonce: str) -> dict[str, Any] | None:
        """Retrieve challenge data by nonce."""
        with self._lock:
            cur = self._conn.cursor()
            cur.execute(
                """
                SELECT nonce, session_id, level, rule_name, regex_str, dfa_signature,
                       positive_examples, negative_examples, test_strings,
                       correct_labels, certificate_data, expires_at, created_at, used
                FROM challenges
                WHERE nonce = ?
                """,
                (nonce,),
            )
            row = cur.fetchone()
            if not row:
                return None
            return {
                "nonce": row["nonce"],
                "session_id": row["session_id"],
                "level": row["level"],
                "rule_name": row["rule_name"],
                "regex_str": row["regex_str"],
                "dfa_signature": row["dfa_signature"],
                "positive_examples": json.loads(row["positive_examples"]),
                "negative_examples": json.loads(row["negative_examples"]),
                "test_strings": json.loads(row["test_strings"]),
                "correct_labels": json.loads(row["correct_labels"]),
                "certificate_data": json.loads(row["certificate_data"]),
                "expires_at": row["expires_at"],
                "created_at": row["created_at"],
                "used": bool(row["used"]),
            }

    def mark_challenge_used(self, nonce: str) -> None:
        """Mark a challenge nonce as used (single-use semantics)."""
        with self._lock:
            cur = self._conn.cursor()
            cur.execute(
                "UPDATE challenges SET used = 1 WHERE nonce = ?",
                (nonce,),
            )
            self._conn.commit()

    def record_attempt(
        self,
        session_id: str,
        nonce: str,
        ip_address: str | None,
        answers: dict[str, str],
        correct_count: int,
        total_tests: int,
        passed: bool,
        error_code: str | None = None,
    ) -> int:
        """Record an attempt audit record with parameterized insert."""
        now = current_timestamp()
        with self._lock:
            cur = self._conn.cursor()
            cur.execute(
                """
                INSERT INTO attempts (
                    session_id, nonce, ip_address, answers,
                    correct_count, total_tests, passed, error_code, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    session_id,
                    nonce,
                    ip_address,
                    json.dumps(answers),
                    correct_count,
                    total_tests,
                    1 if passed else 0,
                    error_code,
                    now,
                ),
            )
            self._conn.commit()
            return cur.lastrowid or 0

    def close(self) -> None:
        """Close database connection."""
        with self._lock:
            self._conn.close()


__all__ = [
    "Database",
]
