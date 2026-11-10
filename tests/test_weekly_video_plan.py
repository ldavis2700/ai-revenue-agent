import importlib.util
from pathlib import Path
from datetime import datetime,timezone,timedelta
import tempfile
import unittest
import sqlite3
spec=importlib.util.spec_from_file_location('weekly',Path(__file__).parents[1]/'scripts/weekly_video_plan.py');w=importlib.util.module_from_spec(spec);spec.loader.exec_module(w)
class WeeklyTests(unittest.TestCase):
 def setUp(self):
  self.t=tempfile.TemporaryDirectory();self.db=w.connect(Path(self.t.name)/'weekly.db');w.init(self.db,'2026-11-16')
  self.now=datetime(2026,11,16,17,tzinfo=timezone.utc)
  self.brief={'genre':'example genre','researched_at':self.now.isoformat(),'sources':[{'channel_id':f'channel{i}','url':f'https://www.youtube.com/watch?v=example000{i}','views':1000,'observed_at':self.now.isoformat()} for i in range(3)],'concepts':[f'Original illustrative lesson about problem number {i:02}' for i in range(27)]}
 def tearDown(self):self.db.close();self.t.cleanup()
 def assign(self):w.assign(self.db,'2026-11-16',self.brief,self.now)
 def test_27_slots_daily_distribution_and_timezone(self):
  rows=w.slots('2026-11-16');self.assertEqual(len(rows),27)
  self.assertEqual([sum(r['due_at'].startswith((datetime(2026,11,16)+timedelta(days=i)).date().isoformat()) for r in rows) for i in range(7)],[4,4,4,4,4,4,3])
  self.assertTrue(all(r['due_at'].endswith('-08:00') for r in rows));self.assertTrue(w.slots('2026-03-09')[0]['due_at'].endswith('-07:00'))
 def test_non_monday_rejected(self):
  with self.assertRaises(ValueError):w.slots('2026-11-17')
 def test_init_idempotent(self):
  w.init(self.db,'2026-11-16');self.assertEqual(w.status(self.db,'2026-11-16')['planned'],27)
 def test_exactly_27_unique_concepts(self):
  self.brief['concepts'][-1]=self.brief['concepts'][0]
  with self.assertRaises(ValueError):self.assign()
  self.assertEqual(w.status(self.db,'2026-11-16')['concepts_assigned'],0)
 def test_stale_research_rejected(self):
  self.brief['researched_at']=(self.now-timedelta(days=8)).isoformat()
  with self.assertRaises(ValueError):self.assign()
 def test_independent_sources(self):
  for s in self.brief['sources']:s['channel_id']='same'
  with self.assertRaises(ValueError):self.assign()
 def test_existing_week_not_overwritten(self):
  self.assign()
  with self.assertRaises(ValueError):self.assign()
 def test_due_requires_qa_and_does_not_dump_backlog(self):
  self.assign();self.assertEqual(w.due(self.db,self.now),[])
  for i in (1,2):w.ready(self.db,f'2026-11-16-{i:02}','https://example.com/video.mp4',self.now.isoformat())
  self.assertEqual(len(w.due(self.db,datetime(2026,11,17,0,tzinfo=timezone.utc))),1)
  self.assertEqual(w.due(self.db,datetime(2026,11,24,0,tzinfo=timezone.utc)),[])
 def evidence(self):return {'status':'completed','platform':'YOUTUBE','video_id':'example0001','post_url':'https://www.youtube.com/watch?v=example0001','publication_id':'actual-connector-receipt','completed_at':self.now.isoformat(),'channel_id':w.CHANNEL}
 def test_receipt_requires_channel_qa_and_is_idempotent(self):
  self.assign();e=self.evidence();slot='2026-11-16-01'
  with self.assertRaises(ValueError):w.receipt(self.db,slot,e)
  w.ready(self.db,slot,'https://example.com/video.mp4',self.now.isoformat())
  e['channel_id']='wrong'
  with self.assertRaises(ValueError):w.receipt(self.db,slot,e)
  e['channel_id']=w.CHANNEL;w.receipt(self.db,slot,e)
  self.assertTrue(w.receipt(self.db,slot,e)['duplicate'])
  self.assertEqual(w.status(self.db,'2026-11-16')['publication_receipts'],1)
 def test_video_cannot_count_twice(self):
  self.assign();e=self.evidence()
  for i in (1,2):w.ready(self.db,f'2026-11-16-{i:02}','https://example.com/video.mp4',self.now.isoformat())
  w.receipt(self.db,'2026-11-16-01',e)
  with self.assertRaises(sqlite3.IntegrityError):w.receipt(self.db,'2026-11-16-02',e)
if __name__=='__main__':unittest.main()
