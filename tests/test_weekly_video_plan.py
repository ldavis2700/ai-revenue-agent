"""Ten originals per week, monthly genre evidence, no destructive ledger resets."""
import importlib.util
from pathlib import Path
from datetime import datetime, timezone, timedelta
import tempfile
import unittest
import sqlite3

spec=importlib.util.spec_from_file_location('weekly',Path(__file__).parents[1]/'scripts/weekly_video_plan.py')
w=importlib.util.module_from_spec(spec)
spec.loader.exec_module(w)

class WeeklyTests(unittest.TestCase):
    def setUp(self):
        self.t=tempfile.TemporaryDirectory()
        self.db=w.connect(Path(self.t.name)/'weekly.db')
        self.week='2026-11-16'
        self.now=datetime(2026,11,16,17,tzinfo=timezone.utc)
        self.source_time=datetime(2026,11,15,17,tzinfo=timezone.utc).isoformat()
        self.monthly={'genre':'original practical technology demonstrations',
          'researched_at':self.source_time,
          'sources':[{'channel_id':f'channel{i}',
                      'url':f'https://www.youtube.com/watch?v=example000{i}',
                      'views':1000+i,
                      'observed_at':self.source_time} for i in range(3)],
          'scope':'sample of three independent channels; not a global ranking'}
        self.brief={'concepts':[f'Original practical workflow lesson illustrating challenge number {i:02}' for i in range(10)]}
        w.init(self.db,self.week)

    def tearDown(self):
        self.db.close()
        self.t.cleanup()

    def research(self):
        return w.record_month(self.db,'2026-11',self.monthly,self.now)

    def assign(self):
        self.research()
        return w.assign(self.db,self.week,self.brief,self.now)

    def evidence(self):
        return {'status':'completed','platform':'YOUTUBE','video_id':'example0001',
                'post_url':'https://www.youtube.com/watch?v=example0001',
                'publication_id':'verified-connector-receipt','completed_at':self.now.isoformat(),
                'channel_id':w.CHANNEL}

    def test_exact_ten_slots_over_seven_days_and_dst(self):
        rows=w.slots(self.week)
        self.assertEqual(len(rows),10)
        self.assertEqual([sum(r['due_at'].startswith((datetime(2026,11,16)+timedelta(days=i)).date().isoformat())
                          for r in rows) for i in range(7)],[2,1,2,1,2,1,1])
        self.assertTrue(all(r['due_at'].endswith('-08:00') for r in rows))
        self.assertTrue(w.slots('2026-03-09')[0]['due_at'].endswith('-07:00'))

    def test_non_monday_rejected(self):
        with self.assertRaises(ValueError):w.slots('2026-11-17')

    def test_init_idempotent(self):
        w.init(self.db,self.week)
        self.assertEqual(w.status(self.db,self.week)['planned'],10)

    def test_monthly_research_required_and_idempotent(self):
        with self.assertRaises(ValueError):w.assign(self.db,self.week,self.brief,self.now)
        first=self.research()
        self.assertTrue(first['recorded'])
        self.assertTrue(self.research()['duplicate'])
        self.assertEqual(self.assign_after_research()['assigned'],10)

    def assign_after_research(self):
        return w.assign(self.db,self.week,self.brief,self.now)

    def test_monthly_genre_conflict_does_not_overwrite(self):
        self.research()
        self.monthly['genre']='another genre'
        with self.assertRaises(ValueError):self.research()
        self.assertEqual(self.db.execute("SELECT genre FROM monthly_genres WHERE month='2026-11'").fetchone()[0],
                         'original practical technology demonstrations')

    def test_three_channels_stale_and_wrong_month_rejected(self):
        for s in self.monthly['sources']:s['channel_id']='same'
        with self.assertRaises(ValueError):self.research()
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM monthly_genres').fetchone()[0],0)
        for i,s in enumerate(self.monthly['sources']):s['channel_id']=f'channel{i}'
        self.monthly['researched_at']=(self.now-timedelta(days=8)).isoformat()
        with self.assertRaises(ValueError):self.research()
        self.monthly['researched_at']=self.source_time
        with self.assertRaises(ValueError):w.record_month(self.db,'2026-12',self.monthly,self.now)

    def test_ten_concepts_exactly_and_uniquely(self):
        self.research()
        self.brief['concepts'].append('Another original lesson with a distinct customer scenario')
        with self.assertRaises(ValueError):self.assign_after_research()
        self.brief['concepts']=self.brief['concepts'][:10]
        self.brief['concepts'][-1]=self.brief['concepts'][0]
        with self.assertRaises(ValueError):self.assign_after_research()
        self.assertEqual(w.status(self.db,self.week)['concepts_assigned'],0)

    def test_no_overwrite_assigned_week(self):
        self.assign()
        with self.assertRaises(ValueError):self.assign_after_research()

    def test_due_requires_media_qa_and_limits_backlog(self):
        self.assign()
        self.assertEqual(w.due(self.db,self.now),[])
        for i in (1,2):
            w.ready(self.db,f'{self.week}-{i:02}','https://example.com/media.mp4',self.now.isoformat())
        self.assertEqual(len(w.due(self.db,datetime(2026,11,17,0,tzinfo=timezone.utc))),1)
        self.assertEqual(w.due(self.db,datetime(2026,11,24,0,tzinfo=timezone.utc)),[])

    def test_receipt_requires_channel_qa_idempotence_and_no_duplicate_video(self):
        self.assign()
        slot=f'{self.week}-01'
        e=self.evidence()
        with self.assertRaises(ValueError):w.receipt(self.db,slot,e)
        w.ready(self.db,slot,'https://example.com/media.mp4',self.now.isoformat())
        e['channel_id']='other'
        with self.assertRaises(ValueError):w.receipt(self.db,slot,e)
        e['channel_id']=w.CHANNEL
        self.assertTrue(w.receipt(self.db,slot,e)['recorded'])
        self.assertTrue(w.receipt(self.db,slot,e)['duplicate'])
        w.ready(self.db,f'{self.week}-02','https://example.com/media.mp4',self.now.isoformat())
        with self.assertRaises(sqlite3.IntegrityError):
            w.receipt(self.db,f'{self.week}-02',e)
        self.assertEqual(w.status(self.db,self.week)['publication_receipts'],1)

    def test_legacy_27_blank_slots_reconciled_without_deletion(self):
        legacy='2026-11-23'
        with self.db:
            self.db.execute('INSERT INTO weeks(week,channel) VALUES (?,?)',(legacy,w.CHANNEL))
            for i in range(1,28):
                self.db.execute("INSERT INTO slots(id,week,due_at) VALUES (?,?,?)",
                                (f'{legacy}-{i:02}',legacy,f'{legacy}T12:00:00-08:00'))
        result=w.init(self.db,legacy)
        self.assertEqual(result['planned_slots'],10)
        self.assertEqual(result['preserved_legacy_rows'],17)
        self.assertEqual(w.status(self.db,legacy)['stored_rows'],27)
        self.assertEqual(w.status(self.db,legacy)['inactive_preserved_rows'],17)
        self.assertEqual(self.db.execute('SELECT due_at FROM slots WHERE id=?',(legacy+'-01',)).fetchone()[0],
                         w.slots(legacy)[0]['due_at'])
        self.assertEqual(w.init(self.db,legacy)['planned_slots'],10)

    def test_legacy_started_extra_kept_and_not_claimed_as_ten(self):
        legacy='2026-11-23'
        with self.db:
            self.db.execute('INSERT INTO weeks(week,channel) VALUES (?,?)',(legacy,w.CHANNEL))
            for i in range(1,28):
                self.db.execute("INSERT INTO slots(id,week,due_at,concept) VALUES (?,?,?,?)",
                                (f'{legacy}-{i:02}',legacy,f'{legacy}T10:00:00-08:00',
                                 'Original started media work' if i==18 else None))
        result=w.init(self.db,legacy)
        self.assertEqual(result['planned_slots'],11)
        self.assertEqual(result['started_surplus'],1)
        self.assertEqual(self.db.execute('SELECT due_at FROM slots WHERE id=?',(legacy+'-01',)).fetchone()[0],
                         f'{legacy}T10:00:00-08:00')
        self.assertEqual(self.db.execute('SELECT concept FROM slots WHERE id=?',(legacy+'-18',)).fetchone()[0],
                         'Original started media work')

if __name__=='__main__':unittest.main()
