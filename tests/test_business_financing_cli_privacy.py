"""Fail-closed CLI regressions: owner financing facts must never be logged."""
import contextlib
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from scripts.business_financing_readiness import main


class FinancingCliPrivacyTests(unittest.TestCase):
    def test_missing_private_output_refuses_stdout(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "approved.json"
            source.write_text(json.dumps({
                "legal_business_name": "SYNTHETIC_PRIVATE_BUSINESS",
                "evidence": {"legal_business_name": {"status": "owner_attested"}},
            }), encoding="utf-8")
            captured_stdout, captured_stderr = io.StringIO(), io.StringIO()
            with patch.object(sys, "argv", ["readiness", str(source)]):
                with contextlib.redirect_stdout(captured_stdout), contextlib.redirect_stderr(captured_stderr):
                    with self.assertRaises(SystemExit) as exit_:
                        main()
            self.assertEqual(exit_.exception.code, 2)
            self.assertNotIn("SYNTHETIC_PRIVATE_BUSINESS", captured_stdout.getvalue())
            self.assertNotIn("SYNTHETIC_PRIVATE_BUSINESS", captured_stderr.getvalue())
            self.assertEqual(captured_stdout.getvalue(), "")

    def test_explicit_owner_only_output_does_not_log_facts(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "approved.json"
            dest = Path(directory) / "financing-report.json"
            source.write_text(json.dumps({
                "legal_business_name": "SYNTHETIC_PRIVATE_BUSINESS",
                "evidence": {"legal_business_name": {"status": "owner_attested"}},
            }), encoding="utf-8")
            captured = io.StringIO()
            with patch.object(sys, "argv", ["readiness", str(source), "--output", str(dest)]):
                with contextlib.redirect_stdout(captured):
                    main()
            self.assertEqual(captured.getvalue(), "")
            self.assertIn("SYNTHETIC_PRIVATE_BUSINESS", dest.read_text(encoding="utf-8"))
            if os.name == "posix":
                self.assertEqual(dest.stat().st_mode & 0o777, 0o600)


if __name__ == "__main__":
    unittest.main()
