#!/usr/bin/env python3
"""Monthly genre evidence and ten-video weekly planning; no implicit publication."""
import argparse
from datetime import date, datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import re
import sqlite3
from zoneinfo import ZoneInfo

TZ=ZoneInfo('America/Los_Angeles')
CHANNEL='UC1TPDWauf7kEnOYjbE1zU7w'
WEEKLY_TARGET=10

def slots(week):
    monday=date.fromisoformat(week)
    if monday.weekday()!=0:raise ValueError('week must be a Monday')
    result=[]
    for day in range(7):
        hours=((12,18),(17,),(12,18),(17,),(17,),(11,18),(14,))[day]
        for hour in hours:
            when=datetime.combine(monday+timedelta(days=day),datetime.min.time(),TZ).replace(hour=hour)
            result.append({'id':f'{week}-{len(result)+1:02}', 'due_at':when.isoformat()})
    return result

def connect(path):
    Path(path).parent.mkdir(parents=True,exist_ok=True)
    db=sqlite3.connect(path,timeout=15);db.row_factory=sqlite3.Row
    db.executescript('''
      CREATE TABLE IF NOT EXISTS weeks (week TEXT PRIMARY KEY, genre TEXT, evidence TEXT, channel TEXT NOT NULL);
      CREATE TABLE IF NOT EXISTS monthly_genres (month TEXT PRIMARY KEY, genre TEXT NOT NULL, evidence TEXT NOT NULL, observed_at TEXT NOT NULL);
      CREATE TABLE IF NOT EXISTS slots (
        id TEXT PRIMARY KEY, week TEXT NOT NULL, due_at TEXT NOT NULL,
        concept TEXT, concept_digest TEXT UNIQUE, job_id TEXT UNIQUE,
        media_url TEXT, qa_at TEXT, published_at TEXT,
        video_id TEXT UNIQUE, receipt TEXT, active INTEGER NOT NULL DEFAULT 1);
    ''')
    if 'active' not in {r['name'] for r in db.execute('PRAGMA table_info(slots)')}:
        db.execute('ALTER TABLE slots ADD COLUMN active INTEGER NOT NULL DEFAULT 1')
    return db

def init(db,week):
    rows=slots(week)
    with db:
        db.execute('INSERT OR IGNORE INTO weeks(week,channel) VALUES (?,?)',(week,CHANNEL))
        db.executemany('INSERT OR IGNORE INTO slots(id,week,due_at) VALUES (?,?,?)',[(s['id'],week,s['due_at']) for s in rows])
    # Never delete historical slots or receipts. Extra legacy slots become inactive
    # unless they already contain a prepared artifact or a publication receipt.
    with db:
        db.execute("""UPDATE slots SET active=0 WHERE week=? AND
             id NOT IN (SELECT id FROM slots WHERE week=? ORDER BY id LIMIT ?) AND
             media_url IS NULL AND receipt IS NULL""",(week,week,WEEKLY_TARGET))
        for item in rows:
            db.execute("""UPDATE slots SET due_at=?,active=1 WHERE id=?
                AND concept IS NULL AND media_url IS NULL AND receipt IS NULL""",
                (item['due_at'],item['id']))
    return {'week':week,'planned_slots':WEEKLY_TARGET,
        'preserved_legacy_slots':db.execute('SELECT COUNT(*) FROM slots WHERE week=? AND active=0',(week,)).fetchone()[0],
        'timezone':str(TZ),'publication_receipts':db.execute('SELECT COUNT(*) FROM slots WHERE week=? AND receipt IS NOT NULL',(week,)).fetchone()[0]}

def aware(value):
    dt=datetime.fromisoformat(value)
    if dt.tzinfo is None:raise ValueError('timestamp requires timezone')
    return dt

def record_monthly_genre(db,month,brief,now=None):
    now=now or datetime.now(timezone.utc)
    if not re.fullmatch(r'\d{4}-\d{2}', month):raise ValueError('invalid month')
    if not isinstance(brief.get('genre'),str) or not brief['genre'].strip():raise ValueError('genre missing')
    observed=aware(brief['researched_at'])
    if observed.astimezone(TZ).strftime('%Y-%m')!=month:raise ValueError('month mismatch')
    if not timedelta(0)<=now-observed<=timedelta(days=7):raise ValueError('stale research')
    sources=brief.get('sources',[])
    if len({s.get('channel_id') for s in sources if s.get('channel_id')})<3:raise ValueError('three independent channels required')
    for source in sources:
        if not re.fullmatch(r'https://(www\.)?youtube\.com/watch\?v=[A-Za-z0-9_-]{11}',source.get('url','')):
            raise ValueError('source URL required')
        if type(source.get('views')) is not int or source['views']<0:raise ValueError('observed views required')
        age=now-aware(source['observed_at'])
        if not timedelta(0)<=age<=timedelta(days=7):raise ValueError('stale observation')
    with db:
        existing=db.execute('SELECT evidence FROM monthly_genres WHERE month=?',(month,)).fetchone()
        if existing:
            if json.loads(existing['evidence'])==brief:return {'month':month,'duplicate':True}
            raise ValueError('month already researched; reconcile without overwrite')
        db.execute('INSERT INTO monthly_genres(month,genre,evidence,observed_at) VALUES(?,?,?,?)',
                   (month,brief['genre'],json.dumps(brief),brief['researched_at']))
    return {'month':month,'genre':brief['genre'],'duplicate':False}

def assign(db,week,brief,now=None):
    """Use the current month's evidence; no fabricated trends or overwritten work."""
    week_date=date.fromisoformat(week)
    month=week_date.strftime('%Y-%m')
    row=db.execute('SELECT * FROM monthly_genres WHERE month=?',(month,)).fetchone()
    if not row:raise ValueError('monthly research evidence required')
    genre=row['genre']
    if brief.get('genre')!=genre:raise ValueError('genre mismatch')
    concepts=brief.get('concepts',[])
    if len(concepts)!=WEEKLY_TARGET:raise ValueError('exactly 10 original concepts required')
    normalized=[' '.join(c.lower().split()) if isinstance(c,str) else '' for c in concepts]
    if any(len(c)<20 or len(c)>1000 for c in concepts if isinstance(c,str)) or any(not isinstance(c,str) for c in concepts):
        raise ValueError('concrete original concepts required')
    digests=[hashlib.sha256(c.encode()).hexdigest() for c in normalized]
    if len(set(digests))!=WEEKLY_TARGET:raise ValueError('duplicate concepts')
    with db:
        week_row=db.execute('SELECT * FROM weeks WHERE week=?',(week,)).fetchone()
        if not week_row:raise ValueError('initialize week first')
        if week_row['genre']:raise ValueError('week already assigned; do not overwrite active work')
        if db.execute('SELECT COUNT(*) FROM slots WHERE week=? AND (concept IS NOT NULL OR qa_at IS NOT NULL OR receipt IS NOT NULL)',(week,)).fetchone()[0]:
            raise ValueError('existing weekly work must be reconciled first')
        db.execute('UPDATE weeks SET genre=?,evidence=? WHERE week=?',
                   (genre,json.dumps({'monthly_genre_month':month,'weekly_concepts':concepts}),week))
        for i,(idea,digest) in enumerate(zip(concepts,digests),1):
            db.execute('UPDATE slots SET concept=?,concept_digest=?,job_id=? WHERE id=? AND active=1',
                       (idea.strip(),digest,f'weekly-{week}-{i:02}',f'{week}-{i:02}'))
    return {'week':week,'assigned':WEEKLY_TARGET,'genre':genre}


def ready(db,slot,media_url,qa_at):
    # This operator action follows actual visual/audio/fact/rights checks in the workflow.
    aware(qa_at)
    if not media_url.startswith('https://'):raise ValueError('HTTPS media required')
    with db:
        row=db.execute('SELECT concept,published_at,active FROM slots WHERE id=?',(slot,)).fetchone()
        if not row or not row['active'] or not row['concept'] or row['published_at']:raise ValueError('slot not eligible')
        db.execute('UPDATE slots SET media_url=?,qa_at=? WHERE id=?',(media_url,qa_at,slot))

def due(db,now=None):
    now=now or datetime.now(timezone.utc)
    result=[]
    for row in db.execute('SELECT * FROM slots WHERE active=1 AND media_url IS NOT NULL AND qa_at IS NOT NULL AND published_at IS NULL ORDER BY due_at'):
        # Never dump an expired backlog onto the channel after a missed week.
        if timedelta(0)<=now-aware(row['due_at'])<timedelta(hours=24):result.append(dict(row))
    # A single hourly operator cycle releases at most one publication candidate.
    return result[:1]

def receipt(db,slot,evidence):
    # Caller must import the actual completed connector receipt after reconciliation.
    # Metadata validation cannot independently establish platform or bank settlement.
    if evidence.get('status')!='completed' or evidence.get('platform')!='YOUTUBE':raise ValueError('completed YouTube receipt required')
    vid=evidence.get('video_id','')
    if not re.fullmatch('[A-Za-z0-9_-]{11}',vid):raise ValueError('video ID required')
    if evidence.get('post_url')!=f'https://www.youtube.com/watch?v={vid}':raise ValueError('receipt URL mismatch')
    if not evidence.get('publication_id'):raise ValueError('connector publication ID required')
    aware(evidence['completed_at'])
    with db:
        row=db.execute('SELECT s.*,w.channel FROM slots s JOIN weeks w USING(week) WHERE s.id=?',(slot,)).fetchone()
        if not row or evidence.get('channel_id')!=row['channel']:raise ValueError('channel mismatch')
        if row['receipt']:
            if json.loads(row['receipt'])==evidence:return {'recorded':False,'duplicate':True}
            raise ValueError('conflicting receipt; reconcile before changing')
        if not row['qa_at']:raise ValueError('media QA required')
        db.execute('UPDATE slots SET published_at=?,video_id=?,receipt=? WHERE id=?',(evidence['completed_at'],vid,json.dumps(evidence),slot))
    return {'recorded':True,'duplicate':False}

def status(db,week):
    rows=[dict(r) for r in db.execute('SELECT * FROM slots WHERE week=? ORDER BY due_at',(week,))]
    return {'week':week,'target':WEEKLY_TARGET,'planned':sum(bool(r['active']) for r in rows),'concepts_assigned':sum(bool(r['concept']) for r in rows),
            'media_ready':sum(bool(r['qa_at']) for r in rows),'publication_receipts':sum(bool(r['receipt']) for r in rows),
            'payout_status':'unverified','publication_mode':'external_authorized_connector','slots':rows}

def main():
    p=argparse.ArgumentParser();p.add_argument('--db',required=True)
    sub=p.add_subparsers(dest='action',required=True)
    for action in ('init','status'):
        q=sub.add_parser(action);q.add_argument('--week',required=True)
    q=sub.add_parser('month');q.add_argument('--month',required=True);q.add_argument('--brief',required=True)
    q=sub.add_parser('assign');q.add_argument('--week',required=True);q.add_argument('--brief',required=True)
    q=sub.add_parser('ready');q.add_argument('--slot',required=True);q.add_argument('--media-url',required=True)
    sub.add_parser('due')
    q=sub.add_parser('receipt');q.add_argument('--slot',required=True);q.add_argument('--file',required=True)
    a=p.parse_args()
    with connect(a.db) as db:
        if a.action=='init':result=init(db,a.week)
        elif a.action=='status':result=status(db,a.week)
        elif a.action=='month':result=record_monthly_genre(db,a.month,json.loads(Path(a.brief).read_text()))
        elif a.action=='assign':result=assign(db,a.week,json.loads(Path(a.brief).read_text()))
        elif a.action=='ready':result=ready(db,a.slot,a.media_url,datetime.now(timezone.utc).isoformat())
        elif a.action=='due':result=due(db)
        else:result=receipt(db,a.slot,json.loads(Path(a.file).read_text()))
    print(json.dumps(result,indent=2))

if __name__=='__main__':main()
