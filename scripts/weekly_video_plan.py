#!/usr/bin/env python3
"""Persistent 27-video weekly planning and receipt tracking; no implicit publication."""
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

def slots(week):
    monday=date.fromisoformat(week)
    if monday.weekday()!=0:raise ValueError('week must be a Monday')
    result=[]
    for day in range(7):
        hours=(12,15,18,21) if day==0 else (9,13,17) if day==6 else (9,12,15,18)
        for hour in hours:
            when=datetime.combine(monday+timedelta(days=day),datetime.min.time(),TZ).replace(hour=hour)
            result.append({'id':f'{week}-{len(result)+1:02}', 'due_at':when.isoformat()})
    return result

def connect(path):
    Path(path).parent.mkdir(parents=True,exist_ok=True)
    db=sqlite3.connect(path,timeout=15);db.row_factory=sqlite3.Row
    db.executescript('''
      CREATE TABLE IF NOT EXISTS weeks (week TEXT PRIMARY KEY, genre TEXT, evidence TEXT, channel TEXT NOT NULL);
      CREATE TABLE IF NOT EXISTS slots (
        id TEXT PRIMARY KEY, week TEXT NOT NULL, due_at TEXT NOT NULL,
        concept TEXT, concept_digest TEXT UNIQUE, job_id TEXT UNIQUE,
        media_url TEXT, qa_at TEXT, published_at TEXT,
        video_id TEXT UNIQUE, receipt TEXT);
    ''')
    return db

def init(db,week):
    rows=slots(week)
    with db:
        db.execute('INSERT OR IGNORE INTO weeks(week,channel) VALUES (?,?)',(week,CHANNEL))
        db.executemany('INSERT OR IGNORE INTO slots(id,week,due_at) VALUES (?,?,?)',[(s['id'],week,s['due_at']) for s in rows])
    return {'week':week,'planned_slots':len(rows),'timezone':str(TZ),'publication_receipts':db.execute('SELECT COUNT(*) FROM slots WHERE week=? AND receipt IS NOT NULL',(week,)).fetchone()[0]}

def aware(value):
    dt=datetime.fromisoformat(value)
    if dt.tzinfo is None:raise ValueError('timestamp requires timezone')
    return dt

def assign(db,week,brief,now=None):
    now=now or datetime.now(timezone.utc)
    if not isinstance(brief.get('genre'),str) or not brief['genre'].strip():raise ValueError('genre missing')
    observed=aware(brief['researched_at'])
    if not timedelta(0)<=now-observed<=timedelta(days=7):raise ValueError('research must be current')
    sources=brief.get('sources',[])
    if len({s.get('channel_id') for s in sources if s.get('channel_id')})<3:raise ValueError('three independent channels required')
    for s in sources:
        if not re.fullmatch(r'https://(www\.)?youtube\.com/watch\?v=[A-Za-z0-9_-]{11}',s.get('url','')):raise ValueError('source URL required')
        if type(s.get('views')) is not int or s['views']<0:raise ValueError('observed views required')
        age=now-aware(s['observed_at'])
        if not timedelta(0)<=age<=timedelta(days=7):raise ValueError('stale observation')
    ideas=brief.get('concepts',[])
    if len(ideas)!=27:raise ValueError('exactly 27 original concepts required')
    digests=[]
    for idea in ideas:
        if not isinstance(idea,str) or not 20<=len(idea.strip())<=1000:raise ValueError('concrete original concept required')
        normalized=' '.join(idea.lower().split())
        digests.append(hashlib.sha256(normalized.encode()).hexdigest())
    if len(set(digests))!=27:raise ValueError('duplicate concepts')
    with db:
        row=db.execute('SELECT * FROM weeks WHERE week=?',(week,)).fetchone()
        if not row:raise ValueError('initialize week first')
        if row['genre']:raise ValueError('week already assigned; do not overwrite active work')
        db.execute('UPDATE weeks SET genre=?,evidence=? WHERE week=?',(brief['genre'],json.dumps(brief),week))
        for i,(idea,digest) in enumerate(zip(ideas,digests),1):
            db.execute('UPDATE slots SET concept=?,concept_digest=?,job_id=? WHERE id=?',(idea.strip(),digest,f'weekly-{week}-{i:02}',f'{week}-{i:02}'))
    return {'week':week,'assigned':27,'genre':brief['genre']}

def ready(db,slot,media_url,qa_at):
    # This operator action follows actual visual/audio/fact/rights checks in the workflow.
    aware(qa_at)
    if not media_url.startswith('https://'):raise ValueError('HTTPS media required')
    with db:
        row=db.execute('SELECT concept,published_at FROM slots WHERE id=?',(slot,)).fetchone()
        if not row or not row['concept'] or row['published_at']:raise ValueError('slot not eligible')
        db.execute('UPDATE slots SET media_url=?,qa_at=? WHERE id=?',(media_url,qa_at,slot))

def due(db,now=None):
    now=now or datetime.now(timezone.utc)
    result=[]
    for row in db.execute('SELECT * FROM slots WHERE media_url IS NOT NULL AND qa_at IS NOT NULL AND published_at IS NULL ORDER BY due_at'):
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
    return {'week':week,'target':27,'planned':len(rows),'concepts_assigned':sum(bool(r['concept']) for r in rows),
            'media_ready':sum(bool(r['qa_at']) for r in rows),'publication_receipts':sum(bool(r['receipt']) for r in rows),
            'payout_status':'unverified','publication_mode':'external_authorized_connector','slots':rows}

def main():
    p=argparse.ArgumentParser();p.add_argument('--db',required=True)
    sub=p.add_subparsers(dest='action',required=True)
    for action in ('init','status'):
        q=sub.add_parser(action);q.add_argument('--week',required=True)
    q=sub.add_parser('assign');q.add_argument('--week',required=True);q.add_argument('--brief',required=True)
    q=sub.add_parser('ready');q.add_argument('--slot',required=True);q.add_argument('--media-url',required=True)
    sub.add_parser('due')
    q=sub.add_parser('receipt');q.add_argument('--slot',required=True);q.add_argument('--file',required=True)
    a=p.parse_args()
    with connect(a.db) as db:
        if a.action=='init':result=init(db,a.week)
        elif a.action=='status':result=status(db,a.week)
        elif a.action=='assign':result=assign(db,a.week,json.loads(Path(a.brief).read_text()))
        elif a.action=='ready':result=ready(db,a.slot,a.media_url,datetime.now(timezone.utc).isoformat())
        elif a.action=='due':result=due(db)
        else:result=receipt(db,a.slot,json.loads(Path(a.file).read_text()))
    print(json.dumps(result,indent=2))

if __name__=='__main__':main()
