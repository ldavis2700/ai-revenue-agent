"""Direct financing CLIs never read unsafe applicant-profile paths."""
import contextlib
import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.business_financing_readiness import read_private_profile
from scripts import business_financing_readiness, business_financing_packet


@unittest.skipUnless(hasattr(os, "getuid"), "Private input requires POSIX ownership")
class PrivateFinancingInputTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.profile = self.root / "approved.json"
        self.profile.write_text("{}", encoding="utf-8")
        self.profile.chmod(0o600)

    def test_owner_only_absolute_profile_is_accepted(self):
        self.assertEqual(read_private_profile(self.profile), {})
        report = self.root / "report.json"
        packet = self.root / "packet.md"
        with patch("sys.argv", ["readiness", str(self.profile), "--output", str(report)]):
            business_financing_readiness.main()
        with patch("sys.argv", ["packet", str(self.profile), "--output", str(packet)]):
            with contextlib.redirect_stdout(io.StringIO()):
                business_financing_packet.main()
        self.assertEqual(json.loads(report.read_text())["readiness"], "evidence_incomplete")
        self.assertIn("MISSING / UNVERIFIED", packet.read_text())
        self.assertEqual(report.stat().st_mode & 0o777, 0o600)
        self.assertEqual(packet.stat().st_mode & 0o777, 0o600)

    def test_group_or_world_access_is_rejected_before_cli_output(self):
        for mode in (0o644, 0o640, 0o604):
            self.profile.chmod(mode)
            with self.subTest(mode=oct(mode)):
                with self.assertRaisesRegex(ValueError, "owner-only"):
                    read_private_profile(self.profile)
                destination = self.root / "must-not-exist.md"
                with patch("sys.argv", ["packet", str(self.profile), "--output", str(destination)]):
                    with self.assertRaises(ValueError):
                        business_financing_packet.main()
                self.assertFalse(destination.exists())

    def test_relative_and_symlink_input_rejected(self):
        rel = Path(os.path.relpath(self.profile))
        with self.assertRaisesRegex(ValueError, "absolute"):
            read_private_profile(rel)
        link = self.root / "link.json"
        link.symlink_to(self.profile)
        with self.assertRaisesRegex(ValueError, "owner-only"):
            read_private_profile(link)
        parent_link = self.root / "linked-dir"
        parent_link.symlink_to(self.root, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "owner-only"):
            read_private_profile(parent_link / "approved.json")

    def test_repo_input_rejected_and_error_does_not_leak_contents(self):
        source = Path(business_financing_readiness.__file__).resolve()
        with self.assertRaisesRegex(ValueError, "outside checkout"):
            read_private_profile(source)

    def test_invalid_json_rejected_without_content_in_error(self):
        self.profile.write_text("{ secret contents", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "invalid JSON") as error:
            read_private_profile(self.profile)
        self.assertNotIn("secret contents", str(error.exception))


if __name__ == "__main__":
    unittest.main()
