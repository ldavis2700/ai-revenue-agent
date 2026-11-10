import importlib.util
from pathlib import Path
from datetime import datetime, timezone, timedelta
import tempfile
import unittest
import sqlite3

spec=importlib.util.spec_from_file_location('weekly',Path(__file__).parents[1]/'scripts/weekly_video_plan.py')
w=importlib.util.module_from_spec(spec);spec.loader.exec_module(w)

class WeeklyTests(unittest.TestCase):
 def setUp(self):
  self.t=tempfile.TemporaryDirectory()
  self.db=w.connect(Path(self.t.name)/'weekly.db')
  self.week='2026-11-16'
  self.now=datetime(2026,11,16,17,tzinfo=timezone.utc)
  self.sources=[{'channel_id':f'channel{i}',
    'url':f'https://www.youtube.com/watch?v=example000{i}',
    'views':1000+i,'observed_at':self.now.isoformat()} for i in range(3)]
  self.month={'genre':'original educational demos','researched_at':self.now.isoformat(),'sources':self.sources}
  self.brief={'genre':self.month['genre'],'concepts':[
    f'Original explanatory workflow tutorial for distinct problem {i:02}' for i in range(10)]}
  w.init(self.db,self.week)
 def tearDown(self):self.db.close();self.t.cleanup()
 def assign(self):
  w.record_monthly_genre(self.db,'2026-11',self.month,self.now)
  return w.assign(self.db,self.week,self.brief,self.now)
 def test_ten_slots_spread_timezone(self):
  rows=w.slots(self.week)
  self.assertEqual(len(rows),10)
  self.assertEqual([sum(r['due_at'].startswith((datetime(2026,11,16)+timedelta(days=i)).date().isoformat()) for r in rows) for i in range(7)],[2,1,2,1,1,2,1])
  self.assertTrue(all(r['due_at'].endswith('-08:00') for r in rows))
  self.assertTrue(w.slots('2026-03-09')[0]['due_at'].endswith('-07:00'))
 def test_non_monday_rejected(self):
  with self.assertRaises(ValueError):w.slots('2026-11-17')
 def test_init_idempotent(self):
  w.init(self.db,self.week)
  self.assertEqual(w.status(self.db,self.week)['planned'],10)
 def test_monthly_evidence_required_and_no_overwrite(self):
  with self.assertRaises(ValueError):w.assign(self.db,self.week,self.brief,self.now)
  self.assertFalse(w.record_monthly_genre(self.db,'2026-11',self.month,self.now)['duplicate'])
  self.assertTrue(w.record_monthly_genre(self.db,'2026-11',self.month,self.now)['duplicate'])
  changed={**self.month,'genre':'changed'}
  with self.assertRaises(ValueError):w.record_monthly_genre(self.db,'2026-11',changed,self.now)
 def test_stale_monthly_evidence_and_wrong_month_rejected(self):
  with self.assertRaises(ValueError):w.record_monthly_genre(self.db,'2026-12',self.month,self.now)
  stale={**self.month,'researched_at':(self.now-timedelta(days=8)).isoformat()}
  with self.assertRaises(ValueError):w.record_monthly_genre(self.db,'2026-11',stale,self.now)
 def test_independent_sources_required(self):
  bad={**self.month,'sources':[{**s,'channel_id':'same'} for s in self.sources]}
  with self.assertRaises(ValueError):w.record_monthly_genre(self.db,'2026-11',bad,self.now)
 def test_week_ten_unique_and_genre_match(self):
  w.record_monthly_genre(self.db,'2026-11',self.month,self.now)
  bad={**self.brief,'concepts':self.brief['concepts'][:-1]}
  with self.assertRaises(ValueError):w.assign(self.db,self.week,bad,self.now)
  bad={**self.brief,'genre':'unknown'}
  with self.assertRaises(ValueError):w.assign(self.db,self.week,bad,self.now)
  self.brief['concepts'][-1]=self.brief['concepts'][0]
  with self.assertRaises(ValueError):w.assign(self.db,self.week,self.brief,self.now)
 def test_assignment_immutable(self):
  self.assign()
  with self.assertRaises(ValueError):self.assign()
 def test_due_requires_qa_and_no_flood(self):
  self.assign();self.assertEqual(w.due(self.db,self.now),[])
  for i in (1,2):w.ready(self.db,f'{self.week}-{i:02}','https://example.com/video.mp4',self.now.isoformat())
  self.assertEqual(len(w.due(self.db,datetime(2026,11,17,0,tzinfo=timezone.utc))),1)
  self.assertEqual(w.due(self.db,datetime(2026,11,24,0,tzinfo=timezone.utc)),[])
 def evidence(self):
  return {'status':'completed','platform':'YOUTUBE','video_id':'example0001',
   'post_url':'https://www.youtube.com/watch?v=example0001',
   'publication_id':'actual-connector-receipt','completed_at':self.now.isoformat(),'channel_id':w.CHANNEL}
 def test_receipts_idempotent_and_deduped(self):
  self.assign();e=self.evidence();slot=f'{self.week}-01'
  with self.assertRaises(ValueError):w.receipt(self.db,slot,e)
  w.ready(self.db,slot,'https://example.com/video.mp4',self.now.isoformat())
  w.receipt(self.db,slot,e)
  self.assertTrue(w.receipt(self.db,slot,e)['duplicate'])
  w.ready(self.db,f'{self.week}-02','https://example.com/video.mp4',self.now.isoformat())
  with self.assertRaises(sqlite3.IntegrityError):w.receipt(self.db,f'{self.week}-02',e)
 def test_legacy_27_slots_migrated_without_dropping_receipts(self):
  with self.db:
   self.db.executemany('INSERT INTO slots(id,week,due_at) VALUES(?,?,?)',
     [(f'{self.week}-{i:02}',self.week,self.now.isoformat()) for i in range(11,28)])
   self.db.execute("UPDATE slots SET video_id=?,receipt=?,published_at=? WHERE id=?",
     ('example0001','{"status":"completed"}',self.now.isoformat(),f'{self.week}-27'))
  x=w.init(self.db,self.week)
  self.assertEqual(x['planned_slots'],11)
  self.assertEqual(x['started_surplus'],1)
  self.assertEqual(w.status(self.db,self.week)['planned'],11)
  self.assertEqual(w.status(self.db,self.week)['publication_receipts'],1)
  self.assertEqual(self.db.execute("SELECT COUNT(*) FROM slots WHERE week=?",(self.week,)).fetchone()[0],27)
  self.assertEqual(self.db.execute("SELECT active FROM slots WHERE id=?",(f'{self.week}-27',)).fetchone()[0],1)
  self.assertEqual(self.db.execute("SELECT active FROM slots WHERE id=?",(f'{self.week}-26',)).fetchone()[0],0)

 def test_legacy_started_concept_survives_and_does_not_retime_other_started_week(self):
  with self.db:
   self.db.executemany('INSERT INTO slots(id,week,due_at) VALUES(?,?,?)',
     [(f'{self.week}-{i:02}',self.week,self.now.isoformat()) for i in range(11,28)])
   self.db.execute("UPDATE slots SET concept=?,job_id=? WHERE id=?",
     ('Meaningful started original lesson','weekly-started',f'{self.week}-18'))
   self.db.execute('UPDATE slots SET due_at=? WHERE id=?',
     (self.now.isoformat(),f'{self.week}-01'))
  result=w.init(self.db,self.week)
  self.assertEqual(result['planned_slots'],11)
  self.assertEqual(result['started_surplus'],1)
  self.assertEqual(self.db.execute('SELECT due_at FROM slots WHERE id=?',(f'{self.week}-01',)).fetchone()[0],
                   self.now.isoformat())
  preserved=self.db.execute('SELECT concept,active FROM slots WHERE id=?',(f'{self.week}-18',)).fetchone()
  self.assertEqual(preserved['concept'],'Meaningful started original lesson')
  self.assertEqual(preserved['active'],1)
  self.assertEqual(self.db.execute('SELECT active FROM slots WHERE id=?',(f'{self.week}-17',)).fetchone()[0],0)
  self.assertEqual(w.init(self.db,self.week)['planned_slots'],11)

if __name__=='__main__':unittest.main()
