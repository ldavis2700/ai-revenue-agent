"""Behavioral regressions for the offline sales demonstration."""
import sqlite3
import tempfile
import unittest
from pathlib import Path

from research_evidence_demo import connect, ingest, pending, review, approved_export


def sample(record_id='sample-1'):
    return {'record_id':record_id,'field_name':'shipping_days','proposed_value':'3',
            'source_label':'fictional supplier email A','excerpt':'Example-only: shipping is 3 business days.'}


class EvidenceReviewTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db = connect(Path(self.temp.name) / 'pilot.sqlite')

    def tearDown(self):
        self.db.close()
        self.temp.cleanup()

    def test_no_autoapproval_or_supabase_write(self):
        ingest(self.db, [sample()])
        self.assertEqual(len(pending(self.db)), 1)
        self.assertEqual(approved_export(self.db), [])

    def test_review_approve_and_traceable_export(self):
        ingest(self.db,[sample()])
        self.assertEqual(review(self.db,'sample-1','approve','Human reviewer')['status'], 'approved')
        out = approved_export(self.db)
        self.assertEqual(out[0]['accepted_value'],'3')
        self.assertEqual(len(out[0]['evidence_sha256']),64)
        self.assertEqual(out[0]['source_label'],'fictional supplier email A')

    def test_correction_requires_human_input(self):
        ingest(self.db,[sample()])
        with self.assertRaises(ValueError):
            review(self.db,'sample-1','correct','Human reviewer')
        review(self.db,'sample-1','correct','Human reviewer','4')
        self.assertEqual(approved_export(self.db)[0]['accepted_value'],'4')

    def test_rejection_is_excluded(self):
        ingest(self.db,[sample()])
        review(self.db,'sample-1','reject','Human reviewer')
        self.assertEqual(approved_export(self.db), [])

    def test_unreviewed_changed_evidence_fails_closed(self):
        ingest(self.db,[sample()])
        changed=sample();changed['excerpt']='Contradictory fictional evidence'
        with self.assertRaises(ValueError):
            ingest(self.db,[changed])
        self.assertEqual(len(pending(self.db)),1)

    def test_invalid_or_duplicate_records_are_refused(self):
        with self.assertRaises(ValueError):
            ingest(self.db,[sample(),sample()])
        self.assertEqual(len(pending(self.db)),0)
        bad=sample();bad['source_label']=''
        with self.assertRaises(ValueError):
            ingest(self.db,[bad])

    def test_repeated_approval_is_idempotent_but_revision_forbidden(self):
        ingest(self.db,[sample()])
        review(self.db,'sample-1','approve','Reviewer')
        self.assertTrue(review(self.db,'sample-1','approve','Reviewer')['idempotent'])
        with self.assertRaises(ValueError):
            review(self.db,'sample-1','correct','Reviewer','new value')
        self.assertEqual(len(approved_export(self.db)),1)

    def test_attempted_sql_injection_is_data_not_code(self):
        evil=sample("id'); DROP TABLE proposals; --")
        ingest(self.db,[evil])
        review(self.db,evil['record_id'],'approve','Reviewer')
        self.assertEqual(len(approved_export(self.db)),1)
        self.assertIsNotNone(self.db.execute("SELECT name FROM sqlite_master WHERE name='proposals'").fetchone())

    def test_pending_and_approved_separated(self):
        ingest(self.db,[sample('a'),sample('b')])
        review(self.db,'a','approve','Reviewer')
        self.assertEqual(len(pending(self.db)),1)
        self.assertEqual(len(approved_export(self.db)),1)

    def test_limit_on_records(self):
        with self.assertRaises(ValueError):
            ingest(self.db,[sample(str(i)) for i in range(101)])
        self.assertEqual(len(pending(self.db)),0)

if __name__ == '__main__':
    unittest.main()
