"""Controller offline tests. Run: python -m unittest discover -s engineering_controller -p 'test_*.py'"""
import os
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path
from controller import database, cycle


class ControllerTests(unittest.TestCase):
    def test_queue_is_durable_and_prioritized(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "jobs.sqlite3"
            db = database(path)
            result = cycle(db)
            self.assertEqual(result["mode"], "dry_run")
            self.assertEqual(result["jobs_queued"], 4)
            self.assertEqual(result["production_mutations"], 0)
            apps = [row[0] for row in db.execute("SELECT app FROM jobs ORDER BY priority")]
            self.assertEqual(apps, ["HAEVEN", "HAEVEN", "APEX", "RMC CLASSICS"])
            db.close()
            db2 = database(path)
            self.assertEqual(db2.execute("SELECT count(*) FROM observations").fetchone()[0], 4)
            self.assertEqual(db2.execute("SELECT count(*) FROM jobs").fetchone()[0], 4)
            db2.close()

    def test_execution_flag_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = database(Path(tmp) / "state.db")
            with patch.dict(os.environ, {"CONTROLLER_EXECUTE": "true"}):
                with self.assertRaises(RuntimeError):
                    cycle(db)
            self.assertEqual(db.execute("SELECT count(*) FROM observations").fetchone()[0], 0)
            db.close()


if __name__ == "__main__":
    unittest.main()
