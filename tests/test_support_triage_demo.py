"""Offline synthetic-support triage regression checks; no external credentials."""
import unittest

from scripts.support_triage_demo import demo, prepare_ticket, safe_audit_event


class SupportTriageDemoTests(unittest.TestCase):
    def test_shipping_extraction_and_routing(self):
        item = prepare_ticket("t-1", "My order #AB-10293 shipping is delayed.")
        self.assertEqual(item.topic, "shipping")
        self.assertEqual(item.order_number, "AB-10293")
        self.assertEqual(item.internal_route, "fulfillment_review")

    def test_urgent_billing_issue_escalates_without_send(self):
        item = prepare_ticket("t-2", "Unauthorized charge for order ID ZX9901")
        self.assertEqual(item.urgency, "high")
        self.assertEqual(item.internal_route, "human_escalation")
        self.assertEqual(item.approval_state, "pending_human_review")
        self.assertFalse(item.auto_sent)
        self.assertTrue(item.needs_human_review)

    def test_no_fake_refund_or_delivery_assertions(self):
        item = prepare_ticket("t-3", "Please refund me now")
        self.assertNotIn("refund processed", item.suggested_reply.lower())
        self.assertNotIn("delivered", item.suggested_reply.lower())
        self.assertEqual(item.language, "unverified")

    def test_unknown_topic_goes_to_general_review(self):
        item = prepare_ticket("t-4", "Hi, I have a question")
        self.assertEqual(item.topic, "other")
        self.assertEqual(item.internal_route, "general_support_review")

    def test_audit_event_excludes_message_and_customer_email(self):
        item = prepare_ticket("t-5", "My email is someone@example.com and order #1245A is missing")
        event = safe_audit_event(item)
        self.assertNotIn("someone@example.com", str(event))
        self.assertNotIn("message", event)
        self.assertFalse(event["auto_sent"])

    def test_audit_omits_potentially_identifying_ticket_id(self):
        # Even a caller-supplied ticket ID can accidentally contain a customer email.
        item = prepare_ticket("customer@example.com", "Please check my order")
        event = safe_audit_event(item)
        self.assertNotIn("ticket_id", event)
        self.assertNotIn("customer@example.com", str(event))
        self.assertEqual(event["approval_state"], "pending_human_review")

    def test_reject_blank_or_oversized_ticket(self):
        for value in ("", " ", "x" * 20001):
            with self.assertRaises(ValueError):
                prepare_ticket("demo", value)

    def test_fixture_records_all_require_review(self):
        fixtures = demo()
        self.assertEqual(len(fixtures), 3)
        self.assertTrue(all(x["approval_state"] == "pending_human_review" for x in fixtures))
        self.assertTrue(all(x["auto_sent"] is False for x in fixtures))


if __name__ == "__main__":
    unittest.main()
