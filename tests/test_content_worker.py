import importlib.util
import json
from pathlib import Path
import tempfile
import threading
import unittest
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from unittest.mock import patch

spec=importlib.util.spec_from_file_location('content_worker',Path(__file__).parents[1]/'content_worker.py')
c=importlib.util.module_from_spec(spec);spec.loader.exec_module(c)

class ContentWorkerTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.old=c.STATE;c.STATE=Path(self.temp.name)/'state';c.STOP=threading.Event();c.initialize()
        self.jobs=Path(self.temp.name)/'jobs';self.jobs.mkdir()
        self.m=json.loads(next((c.ROOT/'content/jobs').glob('*.json')).read_text());self.save()
    def tearDown(self):c.STATE=self.old;self.temp.cleanup()
    def save(self): (self.jobs/'job.json').write_text(json.dumps(self.m))
    def test_traversal_rejected(self):
        self.m['id']='../../escape'
        with self.assertRaises(ValueError):c.validate(self.m)
    def test_rights_required(self):
        self.m['original']=False
        with self.assertRaises(ValueError):c.validate(self.m)
    def test_input_limits(self):
        self.m['scenes'][0]['narration']='x'*241
        with self.assertRaises(ValueError):c.validate(self.m)
    def test_completed_job_not_rendered_twice_after_restart(self):
        def fake(m,p):p.mkdir();(p/'video.mp4').write_bytes(b'video')
        with patch.object(c,'render',side_effect=fake) as render:
            c.cycle(self.jobs);c.initialize();c.cycle(self.jobs)
            self.assertEqual(render.call_count,1)
    def test_uncertain_job_requeued(self):
        c.ingest(self.jobs)
        with c.connect() as db:db.execute("UPDATE jobs SET status='rendering'")
        c.initialize()
        with c.connect() as db:self.assertEqual(db.execute('SELECT status FROM jobs').fetchone()[0],'queued')
    def test_immutable_job_change_not_executed(self):
        c.ingest(self.jobs);self.m['title']='Changed';self.save()
        with patch.object(c,'render') as render:c.cycle(self.jobs);render.assert_not_called()
    def test_duplicate_content_with_different_id_not_rendered(self):
        c.ingest(self.jobs);self.m['id']='another-id';self.save()
        with patch.object(c,'render') as render:c.cycle(self.jobs);render.assert_not_called()
    def test_failure_bounded_and_retry_delayed(self):
        with patch.object(c,'render',side_effect=RuntimeError()) as render:
            c.cycle(self.jobs);c.cycle(self.jobs);self.assertEqual(render.call_count,1)
            with c.connect() as db:db.execute('UPDATE jobs SET attempts=3,updated=0')
            c.cycle(self.jobs);self.assertEqual(render.call_count,1)
    def test_disk_full_never_discards_final_media(self):
        with patch.object(c,'disk_bytes',return_value=c.MAX_DISK+1),patch.object(c,'render') as render:
            c.cycle(self.jobs);render.assert_not_called()
    def test_pause_preserves_queue(self):
        (c.STATE/'pause').touch()
        with patch.object(c,'render') as render:c.cycle(self.jobs);render.assert_not_called()
    def test_combined_health_requires_worker_but_preserves_deliberate_pause(self):
        with c.connect() as db:db.execute('INSERT OR REPLACE INTO health VALUES (1,?)',(c.time.time(),))
        with patch.dict(c.os.environ,{'APEX_REVENUE_WORKER_ENABLED':'true'}):
            with patch('revenue_worker.status',return_value={'state':'waiting','healthy':False}):
                self.assertFalse(c.health()['healthy'])
            with patch('revenue_worker.status',return_value={'state':'paused','healthy':False}):
                self.assertTrue(c.health()['healthy'])
            with patch('revenue_worker.status',return_value={'state':'working','healthy':True,'private':'secret'}):
                self.assertTrue(c.health()['healthy'])
                self.assertNotIn('private',c.health()['revenue_worker'])
    def test_invalid_manifest_does_not_stop_other_jobs(self):
        (self.jobs/'bad.json').write_text('[]')
        self.assertEqual(len(c.ingest(self.jobs)),1)

class ContentHTTPTests(unittest.TestCase):
    save=ContentWorkerTests.save
    def setUp(self):
        ContentWorkerTests.setUp(self)
        self.server=c.HTTPServer(('127.0.0.1',0),c.Handler)
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
        self.url='http://127.0.0.1:'+str(self.server.server_port)
    def tearDown(self):
        self.server.shutdown();self.server.server_close();self.thread.join();ContentWorkerTests.tearDown(self)
    def test_artifact_visibility_and_daily_transfer_cap(self):
        c.ingest(self.jobs)
        path=c.STATE/'artifacts'/self.m['id'];path.mkdir();(path/'video.mp4').write_bytes(b'video')
        target=self.url+'/artifacts/'+self.m['id']+'/video.mp4'
        with self.assertRaises(HTTPError) as e:urlopen(target)
        self.assertEqual(e.exception.code,404)
        with c.connect() as db:db.execute("UPDATE jobs SET status='complete'")
        with patch.object(c,'MAX_EGRESS_DAY',5):
            self.assertEqual(urlopen(target).read(),b'video')
            with self.assertRaises(HTTPError) as e:urlopen(target)
            self.assertEqual(e.exception.code,429)
    def test_traversal_and_arbitrary_files_unavailable(self):
        for path in ['/artifacts/../../queue.db','/queue.db','/artifacts/abc/secret.txt',
                     '/sales/offer.html', '/content_worker.py', '/privacy/../queue.db',
                     '/%2e%2e/queue.db', '/.env']:
            with self.assertRaises(HTTPError) as e:urlopen(self.url+path)
            self.assertEqual(e.exception.code,404)
    def test_public_offer_is_checkout_paused_and_query_cannot_override_it(self):
        with urlopen(self.url+'/?setup=https://evil.example&managed=https://evil.example') as response:
            body=response.read().decode()
            self.assertIn('Online checkout is paused',body)
            self.assertIn('FREE_CUSTOMER_INQUIRY_TRACKER.csv',body)
            self.assertIn('FREE_CUSTOMER_INQUIRY_TRACKER_GUIDE.md',body)
            self.assertIn('without signing up or sharing customer information',body)
            self.assertNotIn('buy.stripe.com',body)
            self.assertNotIn('evil.example',body)
            self.assertNotIn('https://ai-revenue-agent-seven.vercel.app',body)
            self.assertIn(c.PUBLIC_ORIGIN,body)
            self.assertIn('frame-ancestors',response.headers['Content-Security-Policy'])
            self.assertEqual(response.headers['X-Content-Type-Options'],'nosniff')
    def test_response_gap_audit_is_owned_safe_and_linked(self):
        for path in ('/response-gap-audit', '/response-gap-audit.html'):
            with urlopen(self.url+path+'?utm_source=public') as response:
                page=response.read().decode()
                self.assertEqual(response.status,200)
                self.assertIn('Free seven-day response gap audit',page)
                self.assertIn('aggregate counts only',page)
                self.assertIn('utm_source=railway',page)
                self.assertNotIn('fetch(',page)
                self.assertNotIn('localStorage',page)
                self.assertNotIn('buy.stripe.com',page)
                self.assertIn("frame-ancestors 'none'",response.headers['Content-Security-Policy'])
        with urlopen(self.url+'/') as response:
            self.assertIn('href="/response-gap-audit"',response.read().decode())
        with self.assertRaises(HTTPError) as exc:
            urlopen(self.url+'/sales/response-gap-audit.html')
        self.assertEqual(exc.exception.code,404)

    def test_all_public_pages_and_legacy_privacy_alias_are_served(self):
        for path in c.PUBLIC_PAGES:
            with urlopen(self.url+path+'?utm_source=test') as response:
                self.assertEqual(response.status,200)
                self.assertIn(b'<!doctype html>',response.read().lower())
    def test_public_pages_respect_shared_transfer_cap_without_breaking_health(self):
        with patch.object(c,'MAX_EGRESS_DAY',1):
            with self.assertRaises(HTTPError) as exc:urlopen(self.url+'/')
            self.assertEqual(exc.exception.code,429)
            with c.connect() as db:
                db.execute('INSERT INTO health VALUES (1,?)',(c.time.time(),))
                self.assertEqual(db.execute('SELECT bytes FROM egress').fetchone()[0],0)
            self.assertTrue(json.load(urlopen(self.url+'/health'))['healthy'])
    def test_missing_or_oversized_public_asset_fails_closed(self):
        with patch.object(c,'ROOT',Path(self.temp.name)):
            with self.assertRaises(HTTPError) as exc:urlopen(self.url+'/')
            self.assertEqual(exc.exception.code,503)
            sales=Path(self.temp.name)/'sales';sales.mkdir()
            (sales/'offer.html').write_bytes(b'x'*100001)
            with self.assertRaises(HTTPError) as exc:urlopen(self.url+'/')
            self.assertEqual(exc.exception.code,503)
    def test_head_checks_public_pages_and_health_without_transferring_body(self):
        with patch.object(c, 'MAX_EGRESS_DAY', 1):
            for route in ('/', '/offer.html', '/privacy', '/home-services'):
                with urlopen(Request(self.url+route+'?utm_source=monitor', method='HEAD')) as response:
                    self.assertEqual(response.status, 200)
                    self.assertEqual(response.read(), b'')
                    self.assertGreater(int(response.headers['Content-Length']), 0)
                    self.assertIn('frame-ancestors', response.headers['Content-Security-Policy'])
            with c.connect() as db:
                self.assertEqual(db.execute('SELECT COUNT(*) FROM egress').fetchone()[0], 0)
                db.execute('INSERT OR REPLACE INTO health VALUES (1,?)', (c.time.time(),))
            with urlopen(Request(self.url+'/health', method='HEAD')) as response:
                self.assertEqual(response.status, 200)
                self.assertEqual(response.read(), b'')
                self.assertGreater(int(response.headers['Content-Length']), 0)
            with self.assertRaises(HTTPError) as exc:
                urlopen(self.url+'/')
            self.assertEqual(exc.exception.code, 429)

    def test_head_artifact_requires_completed_job_and_does_not_consume_egress(self):
        c.ingest(self.jobs)
        path=c.STATE/'artifacts'/self.m['id'];path.mkdir()
        (path/'video.mp4').write_bytes(b'video')
        url=self.url+'/artifacts/'+self.m['id']+'/video.mp4'
        with self.assertRaises(HTTPError) as exc:
            urlopen(Request(url, method='HEAD'))
        self.assertEqual(exc.exception.code,404)
        with c.connect() as db:
            db.execute("UPDATE jobs SET status='complete'")
        with patch.object(c, 'MAX_EGRESS_DAY', 5):
            with urlopen(Request(url, method='HEAD')) as response:
                self.assertEqual(response.status,200)
                self.assertEqual(int(response.headers['Content-Length']),5)
                self.assertEqual(response.read(),b'')
            self.assertEqual(urlopen(url).read(),b'video')
            with self.assertRaises(HTTPError) as exc:
                urlopen(url)
            self.assertEqual(exc.exception.code,429)
        with self.assertRaises(HTTPError) as exc:
            urlopen(Request(self.url+'/queue.db',method='HEAD'))
        self.assertEqual(exc.exception.code,404)

    def test_stale_heartbeat_is_not_healthy(self):
        with self.assertRaises(HTTPError) as e:urlopen(self.url+'/health')
        self.assertEqual(e.exception.code,503)
        with c.connect() as db:db.execute('INSERT INTO health VALUES (1,?)',(c.time.time(),))
        self.assertTrue(json.load(urlopen(self.url+'/health'))['healthy'])
    def test_stalled_render_is_unhealthy_despite_fresh_heartbeat(self):
        c.ingest(self.jobs)
        with c.connect() as db:
            db.execute('INSERT INTO health VALUES (1,?)',(c.time.time(),))
            db.execute("UPDATE jobs SET status='rendering',updated=?",
                       (c.time.time()-2000,))
        with self.assertRaises(HTTPError) as exc:
            urlopen(self.url+'/health')
        self.assertEqual(exc.exception.code,503)
        details=json.load(exc.exception)
        self.assertTrue(details['rendering_overdue'])
        self.assertFalse(details['healthy'])

    def test_active_render_remains_healthy(self):
        c.ingest(self.jobs)
        with c.connect() as db:
            db.execute('INSERT INTO health VALUES (1,?)',(c.time.time(),))
            db.execute("UPDATE jobs SET status='rendering',updated=?",
                       (c.time.time()-60,))
        details=json.load(urlopen(self.url+'/health'))
        self.assertTrue(details['healthy'])
        self.assertFalse(details['rendering_overdue'])


if __name__=='__main__':unittest.main()
