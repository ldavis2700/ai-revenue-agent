"""Tests use isolated disposable git repos; no provider or network calls."""
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.source_pin_preflight import UnsafeRelease, evaluate, main


class SourcePinPreflightTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.repo = Path(self.temp.name)
        self.command("init", "-q")
        self.command("config", "user.email", "test@example.invalid")
        self.command("config", "user.name", "CI Test")
        self.revisions = []
        for num in range(3):
            (self.repo / "change.txt").write_text(str(num))
            self.command("add", "change.txt")
            self.command("commit", "-qm", f"step-{num}")
            self.revisions.append(self.command("rev-parse", "HEAD").stdout.strip())

    def command(self, *args):
        result = subprocess.run(["git", "-C", str(self.repo), *args],
                                text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        return result

    def test_exact_pinned_revision_passes(self):
        deployed, staged, candidate = self.revisions
        result = evaluate(self.repo, deployed, candidate, candidate)
        self.assertTrue(result["safe_to_apply_exact_tested_source"])
        self.assertEqual(result["staged_behind_candidate_commits"], 0)

    def test_outdated_staged_commit_is_blocked(self):
        deployed, staged, candidate = self.revisions
        result = evaluate(self.repo, deployed, staged, candidate)
        self.assertFalse(result["safe_to_apply_exact_tested_source"])
        self.assertEqual(result["staged_behind_candidate_commits"], 1)
        self.assertIn("STALE", result["reason"])
        self.assertEqual(main(["--repo", str(self.repo), "--deployed-sha", deployed,
                               "--staged-sha", staged, "--candidate-sha", candidate]), 2)

    def test_non_descendant_source_is_blocked(self):
        deployed, staged, candidate = self.revisions
        with self.assertRaisesRegex(UnsafeRelease, "does not descend"):
            evaluate(self.repo, staged, deployed, candidate)

    def test_missing_or_truncated_sha_is_blocked(self):
        deployed, staged, candidate = self.revisions
        with self.assertRaisesRegex(UnsafeRelease, "full lowercase"):
            evaluate(self.repo, deployed, staged[:9], candidate)
        with self.assertRaisesRegex(UnsafeRelease, "absent"):
            evaluate(self.repo, deployed, "f" * 40, candidate)

    def test_diverged_history_is_blocked(self):
        deployed, staged, candidate = self.revisions
        self.command("checkout", "-q", staged)
        (self.repo / "change.txt").write_text("diverged")
        self.command("commit", "-qam", "different")
        different = self.command("rev-parse", "HEAD").stdout.strip()
        with self.assertRaisesRegex(UnsafeRelease, "not an ancestor"):
            evaluate(self.repo, deployed, different, candidate)


if __name__ == "__main__":
    unittest.main()
