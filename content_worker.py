#!/usr/bin/env python3
"""Low-cost, durable original-content renderer. Publishing is a separate stage."""
import argparse
import fcntl
import hashlib
import hmac
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import os
from pathlib import Path
import re
import shutil
import signal
import sqlite3
import subprocess
import tempfile
import textwrap
import threading
import time
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parent
STATE = Path(os.environ.get('CONTENT_STATE_DIR', '/data/content'))
STOP = threading.Event()
MAX_DISK = 600_000_000
MAX_EGRESS_DAY = 100_000_000
PUBLIC_ORIGIN = 'https://apex-content-worker-production.up.railway.app'
PUBLIC_PAGES = {'/': 'offer.html', '/offer.html': 'offer.html'}
for _page in ('privacy', 'home-services', 'industries', 'partners'):
    PUBLIC_PAGES['/' + _page] = _page + '.html'
    PUBLIC_PAGES['/' + _page + '.html'] = _page + '.html'
PUBLIC_PAGES.update({'/academy': 'academy.html', '/academy.html': 'academy.html'})
PUBLIC_ASSETS = {'/sales/academy.css': 'academy.css', '/sales/academy.js': 'academy.js'}

def reserve_egress(size):
    """Keep public pages and existing media within the same daily transfer cap."""
    day = time.strftime('%Y-%m-%d', time.gmtime())
    with connect() as db:
        db.execute('BEGIN IMMEDIATE')
        db.execute('INSERT OR IGNORE INTO egress VALUES (?,0)', (day,))
        used = db.execute('SELECT bytes FROM egress WHERE day=?', (day,)).fetchone()[0]
        if used + size > MAX_EGRESS_DAY:
            return False
        db.execute('UPDATE egress SET bytes=bytes+? WHERE day=?', (size, day))
        db.execute('DELETE FROM egress WHERE day<?',
                   (time.strftime('%Y-%m-%d', time.gmtime(time.time()-86400*7)),))
    return True

def connect():
    db = sqlite3.connect(STATE / 'queue.db', timeout=15)
    db.row_factory = sqlite3.Row
    return db

def initialize():
    STATE.mkdir(parents=True, exist_ok=True)
    (STATE / 'artifacts').mkdir(exist_ok=True)
    with connect() as db:
        db.executescript('''
          CREATE TABLE IF NOT EXISTS jobs (
            id TEXT PRIMARY KEY, digest TEXT UNIQUE, status TEXT, attempts INTEGER DEFAULT 0,
            updated REAL, artifact TEXT, error TEXT);
          CREATE TABLE IF NOT EXISTS health (id INTEGER PRIMARY KEY, heartbeat REAL);
          CREATE TABLE IF NOT EXISTS egress (day TEXT PRIMARY KEY, bytes INTEGER);
        ''')
        db.execute("UPDATE jobs SET status='queued' WHERE status='rendering'")

def validate(m):
    if not re.fullmatch(r'[a-z0-9][a-z0-9-]{2,79}', m.get('id', '')):
        raise ValueError('invalid_id')
    for k, maximum in [('title',100),('description',4000),('rights',1000)]:
        if not isinstance(m.get(k),str) or not 1 <= len(m[k]) <= maximum:
            raise ValueError('invalid_'+k)
    if m.get('original') is not True or m.get('audience') != 'adults':
        raise ValueError('rights_or_audience_missing')
    if m.get('format') not in ('vertical','landscape'):
        raise ValueError('invalid_format')
    scenes = m.get('scenes')
    if not isinstance(scenes,list) or not 2 <= len(scenes) <= 12:
        raise ValueError('invalid_scenes')
    total=0
    for scene in scenes:
        for k,maximum in [('heading',70),('text',170),('narration',240)]:
            if not isinstance(scene.get(k),str) or not 1 <= len(scene[k]) <= maximum:
                raise ValueError('invalid_scene_'+k)
            if any(ord(c)<32 and c not in '\n' for c in scene[k]):
                raise ValueError('control_characters')
        total += len(scene['narration'])
    if total>5000:
        raise ValueError('narration_too_long')
    return hashlib.sha256(json.dumps({k:v for k,v in m.items() if k!='id'},sort_keys=True).encode()).hexdigest()

def ingest(directory):
    accepted=[]
    for path in sorted(Path(directory).glob('*.json'))[:200]:
        try:
            if path.stat().st_size>25000:
                raise ValueError('manifest_too_large')
            m=json.loads(path.read_text())
            digest=validate(m)
            with connect() as db:
                row=db.execute('SELECT digest FROM jobs WHERE id=?',(m['id'],)).fetchone()
                if row and row['digest']!=digest:
                    raise ValueError('immutable_job_changed')
                db.execute("INSERT OR IGNORE INTO jobs(id,digest,status,updated) VALUES (?,?,'queued',?)",(m['id'],digest,time.time()))
            accepted.append(m)
        except (ValueError,TypeError,KeyError,AttributeError,OSError):
            print(json.dumps({'event':'manifest_rejected','file':path.name}),flush=True)
    return accepted

def run(args, cwd):
    # No shell or network media inputs; all arguments come from fixed code.
    process=subprocess.Popen(args,cwd=cwd,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    deadline=time.monotonic()+1800
    try:
        while process.poll() is None:
            if STOP.wait(.25) or time.monotonic()>deadline:
                raise RuntimeError('render_interrupted_or_timeout')
        if process.returncode:
            raise RuntimeError('encoder_failed')
    finally:
        if process.poll() is None:
            process.kill()
        process.wait()

def duration(path):
    return float(subprocess.check_output(['ffprobe','-v','error','-show_entries','format=duration','-of','default=nw=1:nk=1',str(path)],timeout=15))

def stamp(seconds):
    ms=round(seconds*1000)
    return f'{ms//3600000:02}:{ms//60000%60:02}:{ms//1000%60:02},{ms%1000:03}'

def render(m, target):
    from PIL import Image, ImageDraw, ImageFont
    width,height=(720,1280) if m['format']=='vertical' else (1280,720)
    font='/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'
    bold='/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'
    timeline=0; captions=[]; segments=[]
    with tempfile.TemporaryDirectory(prefix='render-',dir=STATE) as temporary:
        work=Path(temporary)
        for i,s in enumerate(m['scenes']):
            (work/'speech.txt').write_text(s['narration'])
            run(['ffmpeg','-y','-v','error','-f','lavfi','-i','flite=textfile=speech.txt:voice=slt','speech.wav'],work)
            seconds=duration(work/'speech.wav')+.4
            im=Image.new('RGB',(width,height),'#101C31'); d=ImageDraw.Draw(im)
            d.text((45,50),'RMC AI WORKSHOP',font=ImageFont.truetype(bold,26),fill='#46E2EF')
            d.multiline_text((45,150 if height==1280 else 115),'\n'.join(textwrap.wrap(s['heading'],22 if width==720 else 38)),font=ImageFont.truetype(bold,42),fill='white',spacing=12)
            d.multiline_text((45,390 if height==1280 else 250),'\n'.join(textwrap.wrap(s['text'],29 if width==720 else 68)),font=ImageFont.truetype(font,31),fill='#BCE9F3',spacing=14)
            d.text((45,height-65),f"{i+1}/{len(m['scenes'])}  |  Original lesson • Synthetic narration",font=ImageFont.truetype(font,17),fill='#AAB6CB')
            d.multiline_text((45,height-310 if height==1280 else 480),'\n'.join(textwrap.wrap(s['narration'],43 if width==720 else 85)),font=ImageFont.truetype(font,24),fill='white',spacing=7)
            im.save(work/'slide.png')
            # Caption timing aligns each complete sentence to its synthesized audio scene.
            caption='\n'.join(textwrap.wrap(s['narration'],42 if width==720 else 80))
            # Full narration also remains available in the transcript; SRT is sidecar.
            captions.append(f'{i+1}\n{stamp(timeline)} --> {stamp(timeline+seconds)}\n{caption}\n')
            segment=f'segment-{i}.mp4';segments.append(segment)
            run(['ffmpeg','-y','-v','error','-loop','1','-framerate','15','-i','slide.png','-i','speech.wav','-t',str(seconds),'-c:v','libx264','-preset','ultrafast','-crf','24','-threads','1','-pix_fmt','yuv420p','-c:a','aac','-b:a','96k','-af','apad',segment],work)
            timeline+=seconds
        (work/'concat.txt').write_text(''.join(f"file '{s}'\n" for s in segments))
        run(['ffmpeg','-y','-v','error','-f','concat','-safe','1','-i','concat.txt','-c','copy','-movflags','+faststart','video.mp4'],work)
        run(['ffmpeg','-v','error','-i','video.mp4','-f','null','-'],work)
        size=(work/'video.mp4').stat().st_size
        if size>30_000_000 or not 10<=duration(work/'video.mp4')<=600:
            raise ValueError('output_bounds')
        target.mkdir()
        shutil.copyfile(work/'video.mp4',target/'video.mp4')
        (target/'captions.srt').write_text('\n'.join(captions))
        manifest={**m,'duration_seconds':timeline,'bytes':size,'sha256':hashlib.sha256((target/'video.mp4').read_bytes()).hexdigest(),'status':'rendered_unpublished','production':'Original graphics; local CMU Flite slt narration; FFmpeg H.264/AAC. No paid API.'}
        (target/'manifest.json').write_text(json.dumps(manifest,indent=2))

def disk_bytes():
    return sum(p.stat().st_size for p in STATE.rglob('*') if p.is_file())

def cycle(directory):
    for m in ingest(directory):
        if STOP.is_set() or (STATE/'pause').exists():
            return
        with connect() as db:
            row=db.execute('SELECT * FROM jobs WHERE id=?',(m['id'],)).fetchone()
            if not row or row['status']=='complete' or row['attempts']>=3:
                continue
            if row['status']=='failed' and time.time()-row['updated']<3600:
                continue
            if disk_bytes()>MAX_DISK or shutil.disk_usage(STATE).free<150_000_000:
                print('{"event":"content_storage_full"}',flush=True);return
            db.execute("UPDATE jobs SET status='rendering',attempts=attempts+1,updated=? WHERE id=?",(time.time(),m['id']))
        target=STATE/'artifacts'/m['id']
        try:
            # A completed artifact survives a crash between rename and DB commit.
            if target.exists():
                shutil.rmtree(target)
            render(m,target)
            with connect() as db:
                db.execute("UPDATE jobs SET status='complete',artifact=?,error=NULL,updated=? WHERE id=?",(m['id'],time.time(),m['id']))
            print(json.dumps({'event':'content_rendered','id':m['id'],'publication':'pending'}),flush=True)
        except Exception:
            if target.exists():shutil.rmtree(target)
            with connect() as db:
                db.execute("UPDATE jobs SET status='failed',error='render_failed',updated=? WHERE id=?",(time.time(),m['id']))
            print(json.dumps({'event':'content_render_failed','id':m['id']}),flush=True)

def artifact_authorized(headers):
    token=os.environ.get('CONTENT_ARTIFACT_TOKEN','')
    authorization=headers.get('Authorization','')
    prefix='Bearer '
    return bool(token) and authorization.startswith(prefix) and hmac.compare_digest(authorization[len(prefix):],token)

def health(include_jobs=False):
    # The heartbeat runs in a separate thread, so a wedged render can otherwise
    # appear healthy indefinitely. Render subprocesses are bounded to 30 minutes.
    now=time.time()
    with connect() as db:
        counts={r['status']:r['count'] for r in db.execute('SELECT status,COUNT(*) AS count FROM jobs GROUP BY status')}
        jobs=[dict(r) for r in db.execute('SELECT id,status,attempts,artifact FROM jobs ORDER BY updated DESC LIMIT 50')] if include_jobs else None
        heartbeat=db.execute('SELECT heartbeat FROM health WHERE id=1').fetchone()
        overdue=db.execute(
            "SELECT COUNT(*) FROM jobs WHERE status='rendering' AND updated<?",
            (now-1900,),
        ).fetchone()[0]
    alive=bool(heartbeat and 0 <= now-heartbeat[0] < 90)
    result={'healthy':alive and not bool(overdue),
            'rendering_overdue':bool(overdue),
            'paused':(STATE/'pause').exists(),
            'queue':{'total':sum(counts.values()),'by_status':counts},
            'publishing':'separate_connector_required','paid_api_usage':False}
    if include_jobs:result['jobs']=jobs
    return result

class Handler(BaseHTTPRequestHandler):
    def log_message(self,*args):pass
    def do_GET(self):
        # Exact allowlist: never map arbitrary URLs onto the repository or /data.
        try:
            public_page = PUBLIC_PAGES.get(urlsplit(self.path).path) or PUBLIC_ASSETS.get(urlsplit(self.path).path)
        except ValueError:
            self.send_error(400);return
        if public_page:
            try:
                with (ROOT/'sales'/public_page).open('rb') as source:
                    body = source.read(100_001)
            except OSError:
                self.send_error(503);return
            if len(body) > 100_000:
                self.send_error(503);return
            body = body.replace(b'https://ai-revenue-agent-seven.vercel.app', PUBLIC_ORIGIN.encode())
            if not reserve_egress(len(body)):
                self.send_error(429);return
            self.connection.settimeout(10)
            self.send_response(200)
            self.send_header('Content-Type', ('text/css; charset=utf-8' if public_page.endswith('.css') else 'application/javascript; charset=utf-8' if public_page.endswith('.js') else 'text/html; charset=utf-8'))
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control', 'public, max-age=300')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Referrer-Policy', 'strict-origin-when-cross-origin')
            self.send_header('Permissions-Policy', 'camera=(), microphone=(), geolocation=()')
            self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; connect-src https://wuzmqruxdclstezitsbf.supabase.co; frame-ancestors 'none'; base-uri 'self'; form-action 'self'")
            self.end_headers()
            try:
                self.wfile.write(body)
            except (OSError, TimeoutError):
                pass
            return
        if self.path in ('/health','/admin/jobs'):
            detailed=self.path=='/admin/jobs'
            if detailed and not os.environ.get('CONTENT_ARTIFACT_TOKEN'):
                self.send_error(503);return
            if detailed and not artifact_authorized(self.headers):
                self.send_response(401);self.send_header('WWW-Authenticate','Bearer');self.send_header('Content-Length','0');self.end_headers();return
            result=health(include_jobs=detailed); body=json.dumps(result).encode()
            self.send_response(200 if result['healthy'] else 503);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body);return
        match=re.fullmatch(r'/artifacts/([a-z0-9][a-z0-9-]{2,79})/(video.mp4|captions.srt|manifest.json)',self.path)
        if not match:self.send_error(404);return
        with connect() as db:
            row=db.execute("SELECT status FROM jobs WHERE id=?",(match[1],)).fetchone()
        path=STATE/'artifacts'/match[1]/match[2]
        if not row or row['status']!='complete' or not path.is_file():self.send_error(404);return
        if not os.environ.get('CONTENT_ARTIFACT_TOKEN'):
            self.send_error(503);return
        if not artifact_authorized(self.headers):
            self.send_response(401);self.send_header('WWW-Authenticate','Bearer');self.send_header('Content-Length','0');self.end_headers();return
        size=path.stat().st_size
        if not reserve_egress(size):self.send_error(429);return
        self.connection.settimeout(10)
        content_type={'video.mp4':'video/mp4','captions.srt':'text/plain','manifest.json':'application/json'}[match[2]]
        self.send_response(200);self.send_header('Content-Length',str(size));self.send_header('Content-Type',content_type);self.send_header('Cache-Control','private, no-store');self.end_headers()
        try:
            with path.open('rb') as source:shutil.copyfileobj(source,self.wfile,64*1024)
        except (OSError,TimeoutError):pass

def heartbeat():
    while not STOP.is_set():
        with connect() as db:db.execute('INSERT OR REPLACE INTO health VALUES (1,?)',(time.time(),))
        STOP.wait(15)

def main():
    p=argparse.ArgumentParser();p.add_argument('--once',action='store_true');p.add_argument('--jobs',default=str(ROOT/'content/jobs'));args=p.parse_args()
    STATE.mkdir(parents=True,exist_ok=True)
    lock=(STATE/'worker.lock').open('a+')
    try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    except BlockingIOError:raise SystemExit('content worker already active')
    initialize()
    # Clean only abandoned scratch files belonging to this renderer, never final media.
    for path in STATE.glob('render-*'):
        if path.is_dir() and not path.is_symlink():shutil.rmtree(path)
    for sig in (signal.SIGTERM,signal.SIGINT):signal.signal(sig,lambda *_:STOP.set())
    threading.Thread(target=heartbeat,daemon=True).start()
    if not args.once:
        server=HTTPServer(('0.0.0.0',int(os.getenv('PORT','8080'))),Handler)
        threading.Thread(target=server.serve_forever,daemon=True).start()
    while not STOP.is_set():
        cycle(args.jobs)
        if args.once:
            with connect() as db:
                total=db.execute('SELECT COUNT(*) FROM jobs').fetchone()[0]
                incomplete=db.execute("SELECT COUNT(*) FROM jobs WHERE status!='complete'").fetchone()[0]
            STOP.set()
            if not total or incomplete:raise SystemExit(1)
            break
        STOP.wait(300)
    STOP.set()
    lock.close()

if __name__=='__main__':main()
