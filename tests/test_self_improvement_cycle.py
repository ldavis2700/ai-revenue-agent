import importlib.util
import sqlite3
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from datetime import datetime,timezone

spec=importlib.util.spec_from_file_location("self_review",Path(__file__).parents[1]/"scripts/self_improvement_cycle.py")
review=importlib.util.module_from_spec(spec)
spec.loader.exec_module(review)

class SelfImprovementTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.db=sqlite3.connect(Path(self.temp.name)/'revenue.db', isolation_level=None)
        self.addCleanup(self.db.close)
        self.db.execute("CREATE TABLE revenue_worker_runs (id INTEGER PRIMARY KEY, status TEXT, stages_json TEXT)")
        self.db.execute("CREATE TABLE payment_receipts (receipt_id TEXT)")
        self.db.execute("CREATE TABLE recurring_payment_receipts (receipt_id TEXT)")

    def test_idempotent_daily_review(self):
        first=review.record_review(self.db,'2026-11-10')
        second=review.record_review(self.db,'2026-11-10')
        self.assertTrue(first['recorded'])
        self.assertFalse(second['recorded'])
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM apex_self_improvement_reviews').fetchone()[0],1)
        self.assertEqual(first['priority'],'runtime_observability')

    def test_failed_stage_prioritized_over_research(self):
        self.db.execute("INSERT INTO revenue_worker_runs VALUES (1,'degraded',?)",
                        ('[{"stage":"learn","status":"failed"},{"stage":"plan","status":"completed"}]',))
        result=review.record_review(self.db,'2026-11-10')
        self.assertEqual(result['priority'],'reliability')
        self.assertIn('learn:failed',result['evidence'])

    def test_no_receipt_means_next_paid_delivery_not_income(self):
        self.db.execute("INSERT INTO revenue_worker_runs VALUES (1,'completed','[]')")
        result=review.record_review(self.db,'2026-11-10')
        self.assertEqual(result['priority'],'first_paid_delivery')
        self.assertIn('no local receipt rows',result['evidence'])
        self.assertIn('non-Stripe',result['next_test'])

    def test_private_diagnostics_never_copied_to_review(self):
        self.db.execute("INSERT INTO revenue_worker_runs VALUES (1,'degraded',?)",
                        ('[{"stage":"execute_authorized_inbound","status":"failed","secret":"private-key"}]',))
        result=review.record_review(self.db,'2026-11-10')
        self.assertNotIn('private-key',str(result))
        self.assertNotIn('private-key',self.db.execute('SELECT evidence FROM apex_self_improvement_reviews').fetchone()[0])

    def test_malformed_stage_records_quarantined(self):
        self.db.execute("INSERT INTO revenue_worker_runs VALUES (1,'degraded','not-json')")
        result=review.record_review(self.db,'2026-11-10')
        self.assertIn('invalid_stages_json',result['evidence'])

    def test_local_receipts_are_not_proof_of_settlement(self):
        self.db.execute("INSERT INTO revenue_worker_runs VALUES (1,'completed','[]')")
        self.db.execute("INSERT INTO payment_receipts VALUES ('local-record')")
        result=review.record_review(self.db,'2026-11-10')
        self.assertEqual(result['priority'],'realized_profitability')
        self.assertIn('external settlement',result['evidence'])

    def test_invalid_review_day_rejected_without_record(self):
        for day in ('2026-11-31','yesterday','2026-11-9'):
            with self.assertRaises(ValueError):
                review.record_review(self.db,day)
        self.assertNotIn('apex_self_improvement_reviews',
                         review._tables(self.db))

    def test_completed_review_is_immutable_for_same_day(self):
        self.db.execute("INSERT INTO revenue_worker_runs VALUES (1,'completed','[]')")
        first=review.record_review(self.db,'2026-11-10')
        self.db.execute("INSERT INTO revenue_worker_runs VALUES (2,'degraded','not-json')")
        second=review.record_review(self.db,'2026-11-10')
        self.assertFalse(second['recorded'])
        self.assertEqual(first['priority'],second['priority'])

    def test_worker_includes_review_stage_without_new_scheduler(self):
        from revenue_worker import STAGES
        self.assertEqual(STAGES[-1],('self_review','scripts/self_improvement_cycle.py'))
        self.assertEqual(len([n for n,_ in STAGES if n=='self_review']),1)

if __name__=='__main__':unittest.main()
