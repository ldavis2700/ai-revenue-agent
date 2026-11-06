import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest

from scripts import revenue_cycle


ROOT = Path(__file__).resolve().parents[1]


class RevenueCycleConsentTests(unittest.TestCase):
    def test_negative_and_ambiguous_values_do_not_grant_permission(self):
        for value in (False, None, '', 'false', ' FALSE ', '0', 'no', 'n',
                      'unknown', 'enabled', 0, 2, -1, 1.0, [], ['true'],
                      {}, {'allowed': True}):
            with self.subTest(value=value):
                self.assertIs(revenue_cycle.normalize({'contact_allowed': value})[
                    'contact_allowed'], False)

    def test_explicit_affirmative_import_formats_remain_supported(self):
        for value in (True, 1, 'true', ' TRUE ', '1', 'yes', 'Y'):
            with self.subTest(value=value):
                self.assertIs(revenue_cycle.normalize({'contact_allowed': value})[
                    'contact_allowed'], True)

    def test_missing_permission_defaults_to_false(self):
        self.assertIs(revenue_cycle.normalize({})['contact_allowed'], False)

    def test_false_string_never_reaches_persisted_contact_queue(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = str(Path(tmp) / 'revenue.db')
            leads = [dict(id=key, contact_allowed=value,
                          company_name='Example business', contact_email=key + '@example.test',
                          industry='Home services', pain_point='Slow inquiry response',
                          website='https://example.test', source='owned_inbound_opt_in')
                     for key, value in [('declined', 'false'), ('allowed', 'true')]]
            env = {**os.environ, 'REVENUE_DB_PATH': db, 'LEADS_JSON': json.dumps(leads),
                   'MIN_LEAD_SCORE': '55', 'MAX_OUTREACH_PER_RUN': '20'}
            result = subprocess.run([sys.executable, 'scripts/revenue_cycle.py'],
                                    cwd=ROOT, env=env, text=True, capture_output=True, check=True)
            output = json.loads(result.stdout)
            self.assertEqual(output['metrics']['qualified'], 2)
            self.assertEqual([x['id'] for x in output['contact_ready']], ['allowed'])
            with sqlite3.connect(db) as conn:
                self.assertEqual(dict(conn.execute('SELECT id,contact_allowed FROM leads')),
                                 {'declined': 0, 'allowed': 1})
            actions = subprocess.run([sys.executable, 'scripts/next_actions.py'],
                                     cwd=ROOT, env=env, text=True, capture_output=True, check=True)
            self.assertEqual([x['lead_id'] for x in json.loads(actions.stdout)['actions']],
                             ['allowed'])


if __name__ == '__main__':
    unittest.main()
