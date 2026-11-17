import unittest
from datetime import date
from task_digest import build_digest, safe_text

D = date(2026, 11, 17)

def task(**changes):
    base = dict(id="one", title="Review source", owner="qa-1", due_date="2026-11-18", visibility="team", status="open", priority="normal")
    base.update(changes)
    return base


class TaskDigestTests(unittest.TestCase):
    def test_team_and_private_isolation(self):
        report = build_digest([task(), task(id="two", title="Confidential strategy", visibility="private")], D)
        self.assertIn("Review source", report["team_message"])
        self.assertNotIn("Confidential", report["team_message"])
        self.assertIn("Confidential", report["direct_messages"]["qa-1"])
        self.assertEqual(report["delivery"], "preview_only_no_network_or_automatic_send")

    def test_due_window_and_urgent(self):
        r = build_digest([task(id="future", due_date="2026-12-31"), task(id="urgent", title="Risk", due_date="2026-12-31", priority="urgent"), task(id="done", status="done")], D)
        self.assertIn("Risk", r["team_message"])
        self.assertNotIn("Review source", r["team_message"])

    def test_invalid_and_duplicates_fail_closed(self):
        for tasks in ([task(), task()], [task(visibility="everyone")], [task(owner="<@U123>")], [task(due_date="tomorrow")]):
            with self.subTest(tasks=tasks), self.assertRaises(ValueError):
                build_digest(tasks, D)

    def test_slack_like_injection_neutralized(self):
        value = safe_text("@channel <@U123> & urgent\nline")
        self.assertNotIn("@", value)
        self.assertNotIn("<", value)
        self.assertNotIn("\n", value)

    def test_deterministic(self):
        entries = [task(id="a"), task(id="b", due_date="2026-11-16")]
        self.assertEqual(build_digest(entries, D), build_digest(list(reversed(entries)), D))


if __name__ == "__main__":
    unittest.main()
