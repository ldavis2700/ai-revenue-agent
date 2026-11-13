"""Financing stage protects existing customer work and owner approval gates."""
from datetime import datetime, timezone
from pathlib import Path
import json
import sqlite3
import tempfile
import unittest
from scripts.business_financing_cycle import cycle
from revenue_worker import STAGES

class FinancingCycleTests(unittest.TestCase):
    def test_stages_preserve_inbound_priority(self):
        names = [n for n, _ in STAGES]
        self.assertEqual(names[0], "execute_authorized_inbound")
        self.assertIn("financing_readiness", names)
        self.assertGreater(names.index("financing_readiness"), names.index("research"))

    def test_empty_input_safe_and_deduplicated(self):
        with tempfile.TemporaryDirectory() as d:
            db = str(Path(d) / "worker.sqlite")
            first = cycle(db, current=datetime(2026, 11, 13, tzinfo=timezone.utc))
            second = cycle(db, current=datetime(2026, 11, 13, tzinfo=timezone.utc))
            self.assertEqual(first["state"], "awaiting_authorized_private_facts")
            self.assertEqual(second["state"], "already_checked")
            with sqlite3.connect(db) as con:
                self.assertEqual(con.execute("SELECT count(*) FROM financing_readiness_cycles").fetchone()[0], 1)

    def test_invalid_sensitive_input_not_saved(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "profile.json"
            path.write_text(json.dumps({"ssn": "DO_NOT_STORE"}))
            db = str(Path(d) / "worker.sqlite")
            state = cycle(db, str(path))
            self.assertEqual(state["state"], "input_invalid")
            raw = Path(db).read_bytes()
            self.assertNotIn(b"DO_NOT_STORE", raw)

if __name__ == "__main__":
    unittest.main()
