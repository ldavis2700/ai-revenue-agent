"""Offline lead recovery demo acceptance tests (no external providers)."""
import importlib.util
from pathlib import Path
import unittest

SOURCE = Path(__file__).resolve().parents[1] / 'scripts' / 'lead_recovery_demo.py'
spec = importlib.util.spec_from_file_location('lead_recovery_demo', SOURCE)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def event(**changes):
    base = {'event_id': 'demo_1', 'received_at': '2026-11-15T19:00:00Z',
            'source': 'web_form', 'category': 'quote', 'request_summary': 'Fictional lawn-care quote'}
    return {**base, **changes}


class LeadRecoveryTests(unittest.TestCase):
    def test_accept_and_no_send(self):
        output = module.build_queue([event()])
        self.assertEqual(output['accepted'], 1)
        self.assertFalse(output['outbound_enabled'])
        self.assertFalse(output['queue'][0]['customer_message_sent'])
        self.assertEqual(output['queue'][0]['review_status'], 'owner_review_required')

    def test_duplicates_and_invalid_events_do_not_enter_queue(self):
        output = module.build_queue([event(), event(), event(event_id='bad id'),
                                     event(event_id='demo_2', source='unknown'),
                                     event(event_id='demo_3', received_at='yesterday')])
        self.assertEqual((output['accepted'], output['rejected']), (1, 4))

    def test_incomplete_and_contact_details_rejected(self):
        output = module.build_queue([{}, event(event_id='demo_2', request_summary='Call 555-123-4567'),
                                     event(event_id='demo_3', request_summary='person@example.org')])
        self.assertEqual(output['accepted'], 0)

    def test_common_contact_patterns_and_control_characters_fail_closed(self):
        unsafe = [
            'Call (415) 555-0123',
            'Call +1 415 555 0123',
            'Text 4155550123',
            'Email person@example.org',
            'Visit https://example.org/private',
            'See www.example.org/record',
            'SSN 123-45-6789',
            'Fictional line\n=HYPERLINK("example")',
            'Fictional line\tdata',
        ]
        records = [event(event_id=f'demo_{i}', request_summary=value)
                   for i, value in enumerate(unsafe)]
        output = module.build_queue(records)
        self.assertEqual(output['accepted'], 0)
        self.assertEqual(output['rejected'], len(unsafe))
        self.assertEqual(output['queue'], [])

    def test_normal_fictional_summary_still_accepted(self):
        output = module.build_queue([event(request_summary='Fictional request for two repair estimates')])
        self.assertEqual(output['accepted'], 1)

    def test_csv_formula_is_not_executable(self):
        output = module.build_queue([event(request_summary='=1+1')])
        self.assertIn("'=1+1", module.to_csv(output))

    def test_bounded(self):
        with self.assertRaises(ValueError):
            module.build_queue([event()] * 101)


if __name__ == '__main__':
    unittest.main()
