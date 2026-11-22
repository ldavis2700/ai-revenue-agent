"""Offline synthetic save reliability fixture; no network, clients, or production credentials.

Demonstrates compare-and-swap revisions, durable idempotent receipts, and
post-commit readback. Not an audit or integration of any buyer's system.
"""
from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from pathlib import Path
from typing import Any

_SAFE_ID = re.compile(r"^[a-zA-Z0-9_-]{1,64}$")


def _safe_id(value: Any, label: str) -> str:
    if not isinstance(value, str) or not _SAFE_ID.fullmatch(value):
        raise ValueError(f"{label} must be an opaque ASCII identifier (1-64 chars)")
    return value


class SyntheticSaveStore:
    """Persist fictional document revisions in a local SQLite database only."""

    def __init__(self, database: str | Path):
        self.database = str(database)
        with self._connect() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS synthetic_documents (
                    id TEXT PRIMARY KEY,
                    revision INTEGER NOT NULL CHECK (revision >= 1),
                    content TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS synthetic_save_attempts (
                    request_id TEXT PRIMARY KEY,
                    document_id TEXT NOT NULL,
                    expected_revision INTEGER NOT NULL,
                    content_sha256 TEXT NOT NULL,
                    receipt_json TEXT NOT NULL
                );
            """)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.database, timeout=5.0)
        conn.execute("PRAGMA busy_timeout = 5000")
        return conn

    def seed(self, document_id: str, content: str) -> None:
        _safe_id(document_id, "document_id")
        if not isinstance(content, str) or not content or len(content) > 500:
            raise ValueError("Provide 1-500 characters of synthetic content")
        with self._connect() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO synthetic_documents(id,revision,content) VALUES(?,1,?)",
                (document_id, content),
            )

    def read(self, document_id: str) -> tuple[int, str] | None:
        _safe_id(document_id, "document_id")
        with self._connect() as conn:
            row = conn.execute(
                "SELECT revision,content FROM synthetic_documents WHERE id=?", (document_id,)
            ).fetchone()
        return (int(row[0]), str(row[1])) if row else None

    def save(
        self,
        document_id: str,
        expected_revision: int,
        content: str,
        request_id: str,
        *,
        simulate_storage_failure: bool = False,
    ) -> dict[str, Any]:
        """Return success only after commit plus independent revision/content readback."""
        _safe_id(document_id, "document_id")
        _safe_id(request_id, "request_id")
        if isinstance(expected_revision, bool) or not isinstance(expected_revision, int) or expected_revision < 1:
            raise ValueError("expected_revision must be a positive integer")
        if not isinstance(content, str) or not content or len(content) > 500:
            raise ValueError("Provide 1-500 characters of synthetic content")
        digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
        conn = self._connect()
        try:
            conn.execute("BEGIN IMMEDIATE")
            prior = conn.execute(
                "SELECT document_id,expected_revision,content_sha256,receipt_json "
                "FROM synthetic_save_attempts WHERE request_id=?", (request_id,)
            ).fetchone()
            if prior:
                conn.rollback()
                if prior[:3] != (document_id, expected_revision, digest):
                    return {"status": "idempotency_key_reused", "persisted": False,
                            "action": "Investigate request identity; do not retry as a new edit"}
                return json.loads(prior[3])
            row = conn.execute(
                "SELECT revision FROM synthetic_documents WHERE id=?", (document_id,)
            ).fetchone()
            if not row:
                receipt: dict[str, Any] = {"status": "not_found", "persisted": False,
                                             "action": "Verify document identifier"}
            elif int(row[0]) != expected_revision:
                receipt = {"status": "conflict", "persisted": False,
                           "current_revision": int(row[0]),
                           "action": "Fetch current revision and reconcile; never overwrite silently"}
            else:
                result = conn.execute(
                    "UPDATE synthetic_documents SET revision=revision+1,content=? "
                    "WHERE id=? AND revision=?", (content, document_id, expected_revision)
                )
                if result.rowcount != 1:
                    raise RuntimeError("CAS update did not affect exactly one row")
                if simulate_storage_failure:
                    raise sqlite3.OperationalError("synthetic pre-commit failure")
                receipt = {"status": "committed_pending_readback", "persisted": False,
                           "current_revision": expected_revision + 1,
                           "action": "Verify durable content after commit"}
            conn.execute(
                "INSERT INTO synthetic_save_attempts "
                "(request_id,document_id,expected_revision,content_sha256,receipt_json) VALUES(?,?,?,?,?)",
                (request_id, document_id, expected_revision, digest, json.dumps(receipt, sort_keys=True)),
            )
            conn.commit()
        except sqlite3.Error:
            conn.rollback()
            return {"status": "storage_error", "persisted": False,
                    "action": "Reconcile storage state before retrying same request ID"}
        finally:
            conn.close()
        if receipt["status"] != "committed_pending_readback":
            return receipt
        try:
            post = self.read(document_id)
        except sqlite3.Error:
            post = None
        if post != (expected_revision + 1, content):
            return {"status": "indeterminate", "persisted": False,
                    "action": "Reconcile actual stored revision/content; never claim success"}
        success = {"status": "saved", "persisted": True,
                   "current_revision": expected_revision + 1,
                   "action": "Save accepted and independently verified locally"}
        # Upgrade committed provisional receipt, atomically. A collision is protected
        # by the same durable request_id and original payload digest.
        with self._connect() as conn:
            conn.execute(
                "UPDATE synthetic_save_attempts SET receipt_json=? WHERE request_id=? "
                "AND content_sha256=?", (json.dumps(success, sort_keys=True), request_id, digest)
            )
        return success


def demo() -> list[dict[str, Any]]:
    """Run with an isolated temporary database (never user or production data)."""
    from tempfile import TemporaryDirectory
    with TemporaryDirectory() as directory:
        store = SyntheticSaveStore(Path(directory) / "synthetic.sqlite")
        store.seed("fictional-brief", "Draft v1")
        return [
            store.save("fictional-brief", 1, "Client A edit", "attempt-a"),
            store.save("fictional-brief", 1, "Client B stale edit", "attempt-b"),
            store.save("fictional-brief", 2, "Failed write", "attempt-c", simulate_storage_failure=True),
            store.save("fictional-brief", 2, "Final approved edit", "attempt-d"),
        ]


if __name__ == "__main__":
    print(json.dumps(demo(), indent=2))
