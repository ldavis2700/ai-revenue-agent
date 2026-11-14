"""Regression tests for the local APEX owner-control boundary."""
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from owner_control import execute


class OwnerControlTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.db = str(Path(self.temp.name) / "revenue_agent.db")

    def test_pause_persists_and_is_idempotent(self):
        with patch.dict(os.environ, {"REVENUE_AGENT_KILL_SWITCH": "false"}):
            self.assertEqual(execute("pause", self.db)["outcome"], "paused")
            self.assertEqual(execute("pause", self.db)["outcome"], "paused")
            self.assertTrue(execute("status", self.db)["paused_by_owner"])
            self.assertFalse(execute("status", self.db)["dispatch_allowed"])
            self.assertEqual(execute("resume", self.db)["outcome"], "resumed")
            self.assertFalse(execute("status", self.db)["paused_by_owner"])

    def test_kill_switch_cannot_be_bypassed_by_resume(self):
        with patch.dict(os.environ, {"REVENUE_AGENT_KILL_SWITCH": "true"}):
            execute("pause", self.db)
            self.assertEqual(execute("resume", self.db)["outcome"],
                             "owner_pause_removed_kill_switch_active")
            self.assertFalse(execute("status", self.db)["dispatch_allowed"])

    def test_status_is_read_only(self):
        execute("status", self.db)
        self.assertFalse(Path(self.db).exists())
        self.assertFalse(Path(self.db + ".owner_audit.jsonl").exists())

    def test_unsupported_action_does_not_mutate_state(self):
        with self.assertRaises(ValueError):
            execute("shell", self.db)
        self.assertFalse(Path(self.db + ".pause").exists())

    def test_audit_records_actions_without_secrets(self):
        execute("pause", self.db)
        execute("resume", self.db)
        log = Path(self.db + ".owner_audit.jsonl")
        entries = [json.loads(line) for line in log.read_text().splitlines()]
        self.assertEqual([entry["action"] for entry in entries], ["pause", "resume"])
        self.assertEqual(set(entries[0]), {"at", "action", "outcome"})


if __name__ == "__main__":
    unittest.main()
