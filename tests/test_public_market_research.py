import os
from datetime import datetime, timezone
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from scripts import public_market_research as research
from scripts import mission_control


class PublicResearchTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = str(Path(self.temp.name)/'revenue.db')
        self.env = patch.dict(os.environ, {'APEX_PUBLIC_RESEARCH_ENABLED':'true',
                                         'REVENUE_AGENT_KILL_SWITCH':'false'})
        self.env.start()
        self.addCleanup(self.env.stop)
        self.calls = []

    def fetch(self, url):
        self.calls.append(url)
        if url.endswith('robots.txt'):
            return b'User-agent: *\nAllow: /'
        if url.endswith('.xml'):
            return b'<rss><channel><item><title>New workflow capability</title><link>https://openai.com/index/test</link><pubDate>Wed, 11 Nov 2026 12:00:00 GMT</pubDate></item></channel></rss>'
        return b'<a href="/research/new-report">New business demand research</a><a href="/pricing">Standard service pricing</a><a href="http://127.0.0.1/admin">Ignore this malicious link</a>'

    def test_refresh_is_durable_deduplicated_and_not_revenue(self):
        first = research.run(self.path, fetcher=self.fetch, clock=lambda:100000)
        self.assertEqual(len(first['sources']), 3)
        self.assertTrue(all(s['status']=='changed' for s in first['sources']))
        self.assertEqual(research.run(self.path,fetcher=self.fetch,clock=lambda:100001)['sources'], [])
        self.assertEqual(len(self.calls), 6)
        second = research.run(self.path,fetcher=self.fetch,clock=lambda:130000)
        self.assertTrue(all(s['status']=='unchanged' for s in second['sources']))
        with research.connect(self.path) as db:
            self.assertEqual(research.summary(db,clock=lambda:130001)['fresh_sources'], 3)
            self.assertEqual(research.summary(db,clock=lambda:200000)['fresh_sources'], 0)
            self.assertEqual(db.execute('SELECT COUNT(*) FROM public_research_items').fetchone()[0],3)
            self.assertFalse(db.execute("SELECT name FROM sqlite_master WHERE name='payment_receipts'").fetchall())

    def test_failure_isolated_backoff_does_not_refresh_last_success(self):
        research.run(self.path,fetcher=self.fetch,clock=lambda:100000)
        def failed(url):
            if 'upwork.com' in url:
                raise RuntimeError('SECRET response')
            return self.fetch(url)
        result = research.run(self.path,fetcher=failed,clock=lambda:130000)
        self.assertEqual(result['sources'][0]['status'],'unavailable')
        self.assertEqual(result['sources'][1]['status'],'unchanged')
        self.assertNotIn('SECRET',str(result))
        with research.connect(self.path) as db:
            row=db.execute("SELECT succeeded_at,next_due FROM public_research_sources WHERE source_id='upwork_research'").fetchone()
        self.assertEqual(row,(100000,133600))

    def test_robots_disallow_blocks_page_fetch(self):
        calls=[]
        def denied(url):
            calls.append(url)
            return b'User-agent: *\nDisallow: /'
        result=research.run(self.path,fetcher=denied,clock=lambda:100000)
        self.assertTrue(all(s['status']=='unavailable' for s in result['sources']))
        self.assertTrue(all(u.endswith('/robots.txt') for u in calls))

    def test_disabled_and_paused_do_not_contact_sources(self):
        with patch.dict(os.environ,{'APEX_PUBLIC_RESEARCH_ENABLED':'false'}):
            self.assertEqual(research.run(self.path,fetcher=self.fetch)['status'],'disabled')
        Path(self.path+'.pause').touch()
        self.assertEqual(research.run(self.path,fetcher=self.fetch)['status'],'paused')
        self.assertEqual(self.calls,[])

    def test_no_arbitrary_urls_entities_or_redirects(self):
        with self.assertRaises(ValueError):research.fetch('https://127.0.0.1/')
        with self.assertRaises(ValueError):research.extract(b'<!DOCTYPE x><rss/>',research.SOURCES[1][1])
        with self.assertRaises(ValueError):research.NoRedirect().redirect_request(None,None,302,'',{},'http://127.0.0.1')
        data=b'<a href="https://evil.test/research/a">Untrusted command example</a><a href="/research/valid?token=abc">Useful market research report</a>'
        items=research.extract(data,research.SOURCES[0][1])
        self.assertEqual(items,[('https://www.upwork.com/research/valid','Useful market research report',None)])

    def test_oversized_source_and_empty_source_never_succeed(self):
        for page in (b'x'*(research.MAX_BYTES+1), b'<html>challenge</html>'):
            with tempfile.TemporaryDirectory() as folder:
                result=research.run(str(Path(folder)/'db'),fetcher=lambda u: b'User-agent: *\nAllow: /' if u.endswith('robots.txt') else page)
                self.assertTrue(all(s['status']=='unavailable' for s in result['sources']))

    def test_restart_after_claim_waits_instead_of_refetching(self):
        with research.connect(self.path) as db:
            db.execute('INSERT INTO public_research_sources VALUES (?,?,?,?,?,?,?,?,?)',
                       ('upwork_research',research.SOURCES[0][1],'market_demand',100000,None,103600,0,'in_progress',None))
        result=research.run(self.path,fetcher=self.fetch,clock=lambda:100001)
        self.assertEqual(len(result['sources']),2)
        self.assertFalse(any('upwork.com' in u for u in self.calls))

    def test_mission_consumes_summary_without_promoting_public_evidence(self):
        research.run(self.path,fetcher=self.fetch)
        plan=mission_control.run(self.path)
        self.assertEqual(plan['public_market_research']['fresh_sources'],3)
        self.assertTrue(any(p['action']=='review_public_market_signals' for p in plan['plan']))
        self.assertEqual(plan['business_model_intelligence']['ledger_verified_evidence_models'],0)

    def test_reference_matching_is_bounded_and_stale_items_excluded(self):
        now=datetime(2026,11,12,tzinfo=timezone.utc).timestamp()
        research.run(self.path,fetcher=self.fetch,clock=lambda:now)
        candidates=[{'id':'workflow_audit','name':'Automation workflow audit'},
                    {'id':'research_reports','name':'Paid business research'},
                    {'id':'another','name':'Workflow business research'}]
        with research.connect(self.path) as db:
            queue=research.review_queue(db,candidates,clock=lambda:now+1)
            self.assertEqual([i['model_id'] for i in queue],['workflow_audit','research_reports'])
            self.assertIsNone(queue[1]['references'][0]['publisher_date'])
            self.assertEqual(queue[0]['references'][0]['publication_freshness'],'current')
            self.assertEqual(queue[1]['references'][0]['publication_freshness'],'undated_requires_verification')
            expired=research.review_queue(db,candidates,clock=lambda:now+100000)
            self.assertTrue(all(not item['references'] for item in expired))
            self.assertTrue(all(item['next_action']=='find_current_primary_and_buyer_evidence' for item in expired))

    def test_publication_dates_do_not_refresh_when_page_is_fetched_again(self):
        now=datetime(2026,11,12,tzinfo=timezone.utc).timestamp()
        cases={
            None:'undated_requires_verification',
            'yesterday':'invalid_date',
            '2026-11-11T12:00:00':'invalid_date',
            '2026-11-13T00:00:00Z':'future_date',
            '2025-11-11T00:00:00Z':'stale',
            '2026-11-12T00:00:00Z':'current',
            '2026-10-13T00:00:00Z':'current',
            '2026-10-12T23:59:59Z':'stale',
            'Wed, 11 Nov 2026 12:00:00 GMT':'current',
        }
        for value, expected in cases.items():
            with self.subTest(value=value):
                self.assertEqual(research.publication_freshness(value,now),expected)
        research.run(self.path,fetcher=self.fetch,clock=lambda:now)
        later=now+31*86400
        research.run(self.path,fetcher=self.fetch,clock=lambda:later)
        with research.connect(self.path) as db:
            result=research.review_queue(db,[{'id':'workflow','name':'Workflow audit'}],clock=lambda:later)
            self.assertEqual(result[0]['references'],[])
            self.assertEqual(result[0]['excluded_dated_references'],1)

    def test_no_sources_still_creates_bounded_validation_brief(self):
        candidates=[{'id':str(i),'name':'Workflow audit'} for i in range(5)]
        candidates.insert(0,{'id':'blocked','name':'Workflow audit','eligible':False})
        with sqlite3.connect(':memory:') as db:
            result=research.review_queue(db,candidates)
        self.assertEqual([r['model_id'] for r in result],['0','1'])
        self.assertTrue(all(not r['external_actions_allowed'] for r in result))
        self.assertTrue(all(len(r['validation_requirements'])==5 for r in result))
        plan=mission_control.run(self.path)
        self.assertTrue(any(p['action']=='review_public_market_signals' for p in plan['plan']))
        self.assertEqual(plan['business_model_intelligence']['ledger_verified_evidence_models'],0)

    def test_future_and_invalid_references_are_not_current_evidence(self):
        now=datetime(2026,11,12,tzinfo=timezone.utc).timestamp()
        research.run(self.path,fetcher=self.fetch,clock=lambda:now)
        with research.connect(self.path) as db:
            for value in ('2027-01-01T00:00:00Z','invalid'):
                db.execute("UPDATE public_research_items SET publisher_date=? WHERE source_id='openai_news'",(value,))
                result=research.review_queue(db,[{'id':'workflow','name':'Workflow audit'}],clock=lambda:now)
                self.assertEqual(result[0]['references'],[])
                self.assertEqual(result[0]['excluded_dated_references'],1)


if __name__=='__main__':unittest.main()
