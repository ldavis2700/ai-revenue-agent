"""Static safety checks for the offline APEX Revenue Rescue demo."""
from pathlib import Path
import unittest

DEMO = Path(__file__).resolve().parents[1] / "sales" / "revenue_rescue_demo.html"

class RevenueRescueDemoTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = DEMO.read_text(encoding="utf-8")

    def test_no_live_submission_or_unapproved_network_destination(self):
        text = self.html.lower()
        for prohibited in ('fetch(', 'xmlhttprequest', 'sendbeacon', 'action="http', 'action="/', 'localstorage', 'sessionstorage'):
            self.assertNotIn(prohibited, text)
        self.assertIn('event.preventDefault()', self.html)

    def test_clear_no_delivery_disclosure(self):
        for phrase in ('No message is sent, stored, or delivered',
                       'No inquiry was transmitted, stored, or booked',
                       'Use fictional test details only'):
            self.assertIn(phrase, self.html)

    def test_accessible_and_mobile_basics(self):
        for phrase in ('name="viewport"', 'aria-live="polite"', 'role="status"',
                       'type="email"', 'type="checkbox"', 'maxlength="500"',
                       'name="robots" content="noindex,nofollow"'):
            self.assertIn(phrase, self.html)

if __name__ == "__main__":
    unittest.main()
