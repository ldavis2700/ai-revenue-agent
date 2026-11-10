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
        self.token=patch.dict(c.os.environ,{'CONTENT_ARTIFACT_TOKEN':'test-content-token'},clear=False);self.token.start()
    def tearDown(self):
        self.token.stop();self.server.shutdown();self.server.server_close();self.thread.join();ContentWorkerTests.tearDown(self)
    def authorized(self,url,token='test-content-token'):
        return urlopen(Request(url,headers={'Authorization':'Bearer '+token}))
    def test_artifact_visibility_and_daily_transfer_cap(self):
        c.ingest(self.jobs)
        path=c.STATE/'artifacts'/self.m['id'];path.mkdir();(path/'video.mp4').write_bytes(b'video')
        target=self.url+'/artifacts/'+self.m['id']+'/video.mp4'
        with self.assertRaises(HTTPError) as e:urlopen(target)
        self.assertEqual(e.exception.code,404)
        with c.connect() as db:db.execute("UPDATE jobs SET status='complete'")
        for request in (target,Request(target,headers={'Authorization':'Bearer wrong'})):
            with self.assertRaises(HTTPError) as e:urlopen(request)
            self.assertEqual(e.exception.code,401)
        with patch.object(c,'MAX_EGRESS_DAY',5):
            response=self.authorized(target)
            self.assertEqual(response.read(),b'video')
            self.assertEqual(response.headers['Cache-Control'],'private, no-store')
            with self.assertRaises(HTTPError) as e:self.authorized(target)
            self.assertEqual(e.exception.code,429)
    def test_missing_artifact_token_fails_closed(self):
        c.ingest(self.jobs)
        path=c.STATE/'artifacts'/self.m['id'];path.mkdir();(path/'video.mp4').write_bytes(b'video')
        with c.connect() as db:db.execute("UPDATE jobs SET status='complete'")
        with patch.dict(c.os.environ,{'CONTENT_ARTIFACT_TOKEN':''}):
            with self.assertRaises(HTTPError) as e:urlopen(self.url+'/artifacts/'+self.m['id']+'/video.mp4')
            self.assertEqual(e.exception.code,503)
    def test_traversal_and_arbitrary_files_unavailable(self):
        for path in ['/artifacts/../../queue.db','/queue.db','/artifacts/abc/secret.txt']:
            with self.assertRaises(HTTPError) as e:urlopen(self.url+path)
            self.assertEqual(e.exception.code,404)
    def test_stale_heartbeat_is_not_healthy(self):
        with self.assertRaises(HTTPError) as e:urlopen(self.url+'/health')
        self.assertEqual(e.exception.code,503)
        with c.connect() as db:db.execute('INSERT INTO health VALUES (1,?)',(c.time.time(),))
        self.assertTrue(json.load(urlopen(self.url+'/health'))['healthy'])

if __name__=='__main__':unittest.main()
