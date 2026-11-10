#!/usr/bin/env python3
"""Private durable monthly-genre and ten-original-video weekly planner; no implicit publication."""
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
DAILY_HOURS=((12,18),(15,),(12,18),(15,),(12,18),(13,),(13,))

def slots(week):
    monday=date.fromisoformat(week)
    if monday.weekday()!=0:raise ValueError('week must be a Monday')
    result=[]
    for day in range(7):
        hours=DAILY_HOURS[day]
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
    db.execute("""CREATE TABLE IF NOT EXISTS monthly_genres (
      month TEXT PRIMARY KEY, genre TEXT NOT NULL,
      researched_at TEXT NOT NULL, evidence TEXT NOT NULL)""")
    columns={row['name'] for row in db.execute('PRAGMA table_info(slots)')}
    if 'active' not in columns:
        db.execute('ALTER TABLE slots ADD COLUMN active INTEGER NOT NULL DEFAULT 1')
    db.commit()
    return db

def _started(row):
    return any(row[k] is not None for k in ('concept','media_url','qa_at','published_at','receipt'))

def init(db,week):
    # Never delete or reset the original 27-slot file. Retain all historical rows.
    planned=slots(week)
    target_ids={r['id'] for r in planned}
    with db:
        db.execute('INSERT OR IGNORE INTO weeks(week,channel) VALUES (?,?)',(week,CHANNEL))
        db.executemany('INSERT OR IGNORE INTO slots(id,week,due_at) VALUES (?,?,?)',
                       [(r['id'],week,r['due_at']) for r in planned])
        rows=list(db.execute('SELECT * FROM slots WHERE week=? ORDER BY id',(week,)))
        any_started=any(_started(r) for r in rows)
        for row in rows:
            if row['id'] in target_ids:
                # Re-time legacy first ten only when absolutely no weekly work has started.
                if not any_started:
                    new_due=next(r['due_at'] for r in planned if r['id']==row['id'])
                    db.execute('UPDATE slots SET due_at=?,active=1 WHERE id=?',(new_due,row['id']))
            elif not _started(row):
                db.execute('UPDATE slots SET active=0 WHERE id=?',(row['id'],))
            # Started surplus slots remain intact, including their active status.
    current=list(db.execute('SELECT * FROM slots WHERE week=?',(week,)))
    return {'week':week,'target':WEEKLY_TARGET,'planned_slots':sum(bool(r['active']) for r in current),
            'preserved_legacy_rows':sum(not bool(r['active']) for r in current),
            'started_surplus':sum(bool(r['active']) and r['id'] not in target_ids for r in current),
            'timezone':str(TZ),'publication_receipts':
            sum(r['receipt'] is not None for r in current)}


def aware(value):
    dt=datetime.fromisoformat(value)
    if dt.tzinfo is None:raise ValueError('timestamp requires timezone')
    return dt

def record_month(db,month,brief,now=None):
    """Record a dated research SAMPLE, not a global winner; never overwrite old evidence."""
    now=now or datetime.now(timezone.utc)
    if not re.fullmatch(r'\d{4}-\d{2}',month):raise ValueError('invalid month')
    if not isinstance(brief.get('genre'),str) or not brief['genre'].strip():raise ValueError('genre missing')
    observed=aware(brief['researched_at'])
    if not timedelta(0)<=now-observed<=timedelta(days=7):raise ValueError('research must be current')
    if observed.astimezone(TZ).strftime('%Y-%m')!=month:raise ValueError('research month mismatch')
    sources=brief.get('sources',[])
    if len(sources)<3 or len({s.get('channel_id') for s in sources if s.get('channel_id')})<3:
        raise ValueError('three independent channels required')
    for source in sources:
        if not re.fullmatch(r'https://(www\.)?youtube\.com/watch\?v=[A-Za-z0-9_-]{11}',source.get('url','')):
            raise ValueError('canonical YouTube source URL required')
        if type(source.get('views')) is not int or source['views']<0:
            raise ValueError('observed views required')
        age=now-aware(source['observed_at'])
        if not timedelta(0)<=age<=timedelta(days=7):raise ValueError('stale observation')
    with db:
        row=db.execute('SELECT * FROM monthly_genres WHERE month=?',(month,)).fetchone()
        if row:
            if json.loads(row['evidence'])!=brief:raise ValueError('monthly research already recorded; reconcile')
            return {'month':month,'genre':row['genre'],'recorded':False,'duplicate':True}
        db.execute('INSERT INTO monthly_genres(month,genre,researched_at,evidence) VALUES (?,?,?,?)',
                   (month,brief['genre'].strip(),brief['researched_at'],json.dumps(brief)))
    return {'month':month,'genre':brief['genre'].strip(),'recorded':True,'duplicate':False}

def assign(db,week,brief,now=None):
    """Create ten distinct concepts from the documented month's research."""
    month=week[:7]
    research=db.execute('SELECT * FROM monthly_genres WHERE month=?',(month,)).fetchone()
    if not research:raise ValueError('monthly research missing: do not invent a genre')
    genre=research['genre']
    if 'genre' in brief and brief['genre']!=genre:raise ValueError('monthly genre mismatch')
    concepts=brief.get('concepts',[])
    if len(concepts)!=WEEKLY_TARGET:raise ValueError('exactly ten original concepts required')
    digests=[]
    for idea in concepts:
        if not isinstance(idea,str) or not 20<=len(idea.strip())<=1000:
            raise ValueError('concrete original concept required')
        digests.append(hashlib.sha256(' '.join(idea.lower().split()).encode()).hexdigest())
    if len(set(digests))!=WEEKLY_TARGET:raise ValueError('duplicate concepts')
    with db:
        row=db.execute('SELECT * FROM weeks WHERE week=?',(week,)).fetchone()
        if not row:raise ValueError('initialize week first')
        if row['genre']:raise ValueError('week already assigned; preserve existing work')
        candidates=list(db.execute('SELECT * FROM slots WHERE week=? AND active=1 ORDER BY due_at',(week,)))
        if len(candidates)!=WEEKLY_TARGET or any(_started(r) for r in candidates):
            raise ValueError('weekly slot conflict: preserve and reconcile before assignment')
        db.execute('UPDATE weeks SET genre=?,evidence=? WHERE week=?',
                   (genre,research['evidence'],week))
        for row,idea,digest in zip(candidates,concepts,digests):
            db.execute('UPDATE slots SET concept=?,concept_digest=?,job_id=? WHERE id=?',
                       (idea.strip(),digest,f'weekly-{row["id"]}',row['id']))
    return {'week':week,'assigned':WEEKLY_TARGET,'genre':genre,'month':month}


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
    active=[row for row in rows if row['active']]
    monthly=db.execute('SELECT month,genre,researched_at FROM monthly_genres WHERE month=?',(week[:7],)).fetchone()
    return {'week':week,'target':WEEKLY_TARGET,'planned':len(active),'stored_rows':len(rows),
            'inactive_preserved_rows':len(rows)-len(active),
            'concepts_assigned':sum(bool(row['concept']) for row in active),
            'media_ready':sum(bool(row['qa_at']) for row in active),
            'publication_receipts':sum(bool(row['receipt']) for row in rows),
            'monthly_research':dict(monthly) if monthly else None,
            'payout_status':'unverified','publication_mode':'external_authorized_connector',
            'slots':rows}


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
        elif a.action=='month':result=record_month(db,a.month,json.loads(Path(a.brief).read_text()))
        elif a.action=='assign':result=assign(db,a.week,json.loads(Path(a.brief).read_text()))
        elif a.action=='ready':result=ready(db,a.slot,a.media_url,datetime.now(timezone.utc).isoformat())
        elif a.action=='due':result=due(db)
        else:result=receipt(db,a.slot,json.loads(Path(a.file).read_text()))
    print(json.dumps(result,indent=2))

if __name__=='__main__':main()
