import unittest

from autonomous_cycle import route


class AutonomousCycleTests(unittest.TestCase):
    def test_owned_inbound_initial_message_is_dispatchable(self):
        actions = [{"lead_id": "in_1", "action": "send_initial", "email": "buyer@example.com"}]
        dispatched, review, blocked = route(actions, {"in_1": "owned_inbound_opt_in"}, cap=20)
        self.assertEqual(len(dispatched), 1)
        self.assertEqual(review, [])
        self.assertEqual(blocked, [])

    def test_external_source_never_dispatches_automatically(self):
        actions = [{"lead_id": "cold_1", "action": "send_initial", "email": "buyer@example.com"}]
        dispatched, review, blocked = route(actions, {"cold_1": "external"}, cap=20)
        self.assertEqual(dispatched, [])
        self.assertEqual(review[0]["review_reason"], "source_not_verified_owned_inbound")
        self.assertEqual(blocked, [])

    def test_kill_switch_fails_closed(self):
        actions = [{"lead_id": "in_1", "action": "send_checkout", "email": "buyer@example.com"}]
        dispatched, review, blocked = route(
            actions, {"in_1": "owned_inbound_opt_in"}, kill_switch=True, cap=20
        )
        self.assertEqual(dispatched, [])
        self.assertEqual(review, [])
        self.assertEqual(blocked[0]["blocked_reason"], "autonomy_disabled")

    def test_per_run_cap_is_enforced(self):
        actions = [
            {"lead_id": "in_1", "action": "send_initial", "email": "one@example.com"},
            {"lead_id": "in_2", "action": "send_initial", "email": "two@example.com"},
        ]
        dispatched, _, blocked = route(
            actions,
            {"in_1": "owned_inbound_opt_in", "in_2": "owned_inbound_opt_in"},
            cap=1,
        )
        self.assertEqual(len(dispatched), 1)
        self.assertEqual(blocked[0]["blocked_reason"], "per_run_dispatch_cap_reached")


if __name__ == "__main__":
    unittest.main()
