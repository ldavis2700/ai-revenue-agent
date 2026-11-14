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

    def test_symlink_and_relative_paths_are_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            original = root / "approved.json"
            original.write_text(json.dumps({"legal_business_name": "Fixture only"}))
            linked = root / "symlink.json"
            try:
                linked.symlink_to(original)
            except (OSError, NotImplementedError):
                self.skipTest("Symlinks unavailable")
            state = cycle(str(root / "symlink.sqlite"), str(linked))
            self.assertEqual(state["state"], "input_unavailable")
            state = cycle(str(root / "relative.sqlite"), "approved.json")
            self.assertEqual(state["state"], "input_unavailable")

    def test_private_file_permissions_and_same_day_correction(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            profile = root / "owner_only.json"
            profile.write_text(json.dumps({"ssn": "DO_NOT_STORE"}))
            profile.chmod(0o644)
            db = str(root / "ledger.sqlite")
            now = datetime(2026, 11, 14, tzinfo=timezone.utc)
            first = cycle(db, str(profile), current=now)
            self.assertEqual(first["state"], "input_unavailable")
            profile.chmod(0o600)
            second = cycle(db, str(profile), current=now)
            self.assertEqual(second["state"], "input_invalid")
            self.assertEqual(cycle(db, current=now)["state"], "already_checked")
            with sqlite3.connect(db) as con:
                self.assertEqual(con.execute(
                    "SELECT count(*) FROM financing_readiness_cycles").fetchone()[0], 1)
                self.assertEqual(con.execute(
                    "SELECT state FROM financing_readiness_cycles").fetchone()[0], "input_invalid")
            self.assertNotIn(b"DO_NOT_STORE", Path(db).read_bytes())

    def test_invalid_sensitive_input_not_saved(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "profile.json"
            path.write_text(json.dumps({"ssn": "DO_NOT_STORE"}))
            path.chmod(0o600)
            db = str(Path(d) / "worker.sqlite")
            state = cycle(db, str(path))
            self.assertEqual(state["state"], "input_invalid")
            raw = Path(db).read_bytes()
            self.assertNotIn(b"DO_NOT_STORE", raw)

if __name__ == "__main__":
    unittest.main()
