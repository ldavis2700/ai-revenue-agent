#!/usr/bin/env python3
"""Bounded primary-source discovery. Public signals are never buyer/payment evidence."""
import hashlib
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
import ipaddress
import json
import os
import re
from pathlib import Path
import socket
import sqlite3
import time
from urllib.parse import urljoin, urlsplit
from urllib.request import Request, build_opener, HTTPRedirectHandler, ProxyHandler
from urllib.robotparser import RobotFileParser
import xml.etree.ElementTree as ET

SOURCES = (
    ('upwork_research', 'https://www.upwork.com/research', 'market_demand'),
    ('openai_news', 'https://openai.com/news/rss.xml', 'technical_capability'),
    ('stripe_pricing', 'https://stripe.com/pricing', 'delivery_cost'),
)
USER_AGENT = 'APEXResearch/1.0'
MAX_BYTES = 1_048_576
REFRESH_SECONDS = 21600
PUBLICATION_MAX_AGE_DAYS = 30


def publication_freshness(value, now):
    """A new fetch does not make an old article current market evidence."""
    if not value:
        return 'undated_requires_verification'
    try:
        try:
            published = datetime.fromisoformat(value.replace('Z', '+00:00'))
        except ValueError:
            published = parsedate_to_datetime(value)
        # Do not invent a timezone for ambiguous publisher timestamps.
        if published.tzinfo is None:
            return 'invalid_date'
        age = now - published.astimezone(timezone.utc).timestamp()
    except (TypeError, ValueError, OverflowError):
        return 'invalid_date'
    if age < 0:
        return 'future_date'
    return 'current' if age <= PUBLICATION_MAX_AGE_DAYS * 86400 else 'stale'


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError('redirect_requires_review')


def fetch(url):
    # Only compiled-in source/robots URLs are requestable. Extracted links are
    # references for review, never followed and never interpreted as commands.
    allowed = {s[1] for s in SOURCES}
    allowed.update(urljoin(s[1], '/robots.txt') for s in SOURCES)
    if url not in allowed:
        raise ValueError('source_not_allowed')
    host = urlsplit(url).hostname
    addresses = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
    if not addresses or any(not ipaddress.ip_address(a[4][0]).is_global for a in addresses):
        raise ValueError('non_public_address')
    opener = build_opener(ProxyHandler({}), NoRedirect())
    with opener.open(Request(url, headers={'User-Agent': USER_AGENT,
                                          'Accept-Encoding': 'identity'}), timeout=8) as response:
        content_type = response.headers.get('Content-Type', '').lower()
        if not any(t in content_type for t in ('text/', 'xml', 'json')):
            raise ValueError('unsupported_content_type')
        body = response.read(MAX_BYTES + 1)
        if len(body) > MAX_BYTES:
            raise ValueError('source_too_large')
        return body


class PageLinks(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links, self.href, self.parts = [], None, []

    def handle_starttag(self, tag, attrs):
        if tag == 'a':
            self.href, self.parts = dict(attrs).get('href'), []

    def handle_data(self, data):
        if self.href and len(self.parts) < 20:
            self.parts.append(data[:200])

    def handle_endtag(self, tag):
        if tag == 'a':
            if self.href and len(self.links) < 500:
                self.links.append((self.href, ' '.join(self.parts), None))
            self.href, self.parts = None, []


def extract(body, url):
    """Keep bounded titles/links only; no article bodies or unsupported earnings claims."""
    if url.endswith('.xml'):
        if b'<!DOCTYPE' in body.upper() or b'<!ENTITY' in body.upper():
            raise ValueError('xml_entities_forbidden')
        root = ET.fromstring(body)
        links = [(i.findtext('link', ''), i.findtext('title', ''), i.findtext('pubDate'))
                 for i in root.findall('.//item')[:100]]
    else:
        parser = PageLinks()
        parser.feed(body.decode('utf-8', errors='replace'))
        links = parser.links
    result = {}
    for target, title, published in links:
        target = urljoin(url, target)
        parsed = urlsplit(target)
        if (parsed.scheme != 'https' or parsed.hostname != urlsplit(url).hostname
                or parsed.username or parsed.password or parsed.port not in (None, 443)):
            continue
        # Ignore navigation/tracking links; only source-relevant pages survive.
        if url == SOURCES[0][1] and not parsed.path.startswith('/research/'):
            continue
        if url == SOURCES[2][1] and not any(x in parsed.path for x in ('pricing', 'fees')):
            continue
        title = ' '.join(title.split())[:200]
        if len(title) < 12:
            continue
        clean = parsed._replace(query='', fragment='').geturl()
        result[clean] = (clean, title, (published or '')[:100] or None)
        if len(result) == 50:
            break
    return list(result.values())


def connect(path):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path, timeout=5)
    db.executescript('''
        CREATE TABLE IF NOT EXISTS public_research_sources (
          source_id TEXT PRIMARY KEY, url TEXT NOT NULL, topic TEXT NOT NULL,
          attempted_at REAL NOT NULL, succeeded_at REAL, next_due REAL NOT NULL,
          failures INTEGER NOT NULL, status TEXT NOT NULL, digest TEXT);
        CREATE TABLE IF NOT EXISTS public_research_items (
          source_id TEXT NOT NULL, url TEXT NOT NULL, title TEXT NOT NULL,
          publisher_date TEXT, discovered_at REAL NOT NULL, last_seen_at REAL NOT NULL,
          PRIMARY KEY(source_id,url));
    ''')
    return db


def run(path, *, fetcher=fetch, clock=time.time):
    if os.getenv('APEX_PUBLIC_RESEARCH_ENABLED', 'false').lower() != 'true':
        return {'status': 'disabled', 'external_actions_allowed': False}
    if os.getenv('REVENUE_AGENT_KILL_SWITCH', 'false').lower() == 'true' or Path(str(path)+'.pause').exists():
        return {'status': 'paused', 'external_actions_allowed': False}
    results = []
    with connect(path) as db:
        for source_id, url, topic in SOURCES:
            if os.getenv('REVENUE_AGENT_KILL_SWITCH', 'false').lower() == 'true' or Path(str(path)+'.pause').exists():
                break
            stamp = clock()
            # Durable claim prevents overlapping runs and hot retries after a crash.
            db.execute('BEGIN IMMEDIATE')
            old = db.execute('SELECT next_due,failures,succeeded_at,digest FROM public_research_sources WHERE source_id=?', (source_id,)).fetchone()
            if old and stamp < old[0]:
                db.commit()
                continue
            failures = old[1] if old else 0
            db.execute('INSERT OR REPLACE INTO public_research_sources VALUES (?,?,?,?,?,?,?,?,?)',
                       (source_id, url, topic, stamp, old[2] if old else None,
                        stamp+3600, failures, 'in_progress', old[3] if old else None))
            db.commit()
            try:
                robots = RobotFileParser()
                robots.parse(fetcher(urljoin(url, '/robots.txt')).decode('utf-8').splitlines())
                if not robots.can_fetch(USER_AGENT, url):
                    raise ValueError('robots_disallowed')
                body = fetcher(url)
                if len(body) > MAX_BYTES:
                    raise ValueError('source_too_large')
                items = extract(body, url)
                if not items:
                    raise ValueError('no_research_items')
                # Stable semantic hash ignores rotating HTML, ads and tracking IDs.
                digest = hashlib.sha256(json.dumps(sorted(items)).encode()).hexdigest()
                changed = not old or old[3] != digest
                for target, title, published in items:
                    db.execute('''INSERT INTO public_research_items VALUES (?,?,?,?,?,?)
                        ON CONFLICT(source_id,url) DO UPDATE SET title=excluded.title,
                        publisher_date=excluded.publisher_date,last_seen_at=excluded.last_seen_at''',
                        (source_id, target, title, published, stamp, stamp))
                db.execute('UPDATE public_research_sources SET succeeded_at=?,next_due=?,failures=0,status=?,digest=? WHERE source_id=?',
                           (stamp, stamp+REFRESH_SECONDS, 'changed' if changed else 'unchanged', digest, source_id))
                results.append({'source': source_id, 'status': 'changed' if changed else 'unchanged', 'items': len(items)})
            except Exception:
                db.rollback()
                # Raw responses and exceptions can contain untrusted text; omit them.
                failures = min(failures+1, 6)
                db.execute('UPDATE public_research_sources SET next_due=?,failures=?,status=? WHERE source_id=?',
                           (stamp+min(86400, 3600*2**(failures-1)), failures, 'unavailable', source_id))
                results.append({'source': source_id, 'status': 'unavailable'})
            db.execute('''DELETE FROM public_research_items WHERE rowid NOT IN
                (SELECT rowid FROM public_research_items ORDER BY last_seen_at DESC,rowid DESC LIMIT 500)''')
            db.commit()
    return {'status': 'checked', 'sources': results, 'external_actions_allowed': False,
            'meaning': 'Discovery signals only; no verified customer demand or profitability.'}


def summary(db, clock=time.time):
    try:
        rows = db.execute('SELECT source_id,status,succeeded_at FROM public_research_sources').fetchall()
        total = db.execute('SELECT COUNT(*) FROM public_research_items').fetchone()[0]
    except sqlite3.OperationalError:
        return {'sources_checked': 0, 'fresh_sources': 0, 'items': 0, 'status': 'not_started'}
    return {'sources_checked': len(rows), 'fresh_sources': sum(
        row[2] is not None and 0 <= clock()-row[2] < 2*REFRESH_SECONDS for row in rows),
        'unavailable_sources': sum(row[1] == 'unavailable' for row in rows),
        'items': total, 'status': 'discovery_only'}


def review_queue(db, candidates, clock=time.time):
    """Link eligible catalog candidates to fresh public references, not earned income.

    Keyword matches only route research. Keep the receipt-backed candidate order;
    no match increases a profitability score, satisfies capability QA or grants
    permission to execute. Titles remain untrusted data for the reviewing agent.
    """
    now = clock()
    try:
        rows = db.execute('''SELECT i.url,i.title,i.publisher_date,s.topic
            FROM public_research_items i JOIN public_research_sources s USING(source_id)
            WHERE s.succeeded_at BETWEEN ? AND ? AND i.last_seen_at=s.succeeded_at
            ORDER BY i.discovered_at DESC,i.url LIMIT 150''',
            (now-2*REFRESH_SECONDS, now)).fetchall()
    except sqlite3.OperationalError:
        rows = []
    ignored = {'ai','the','and','for','service','services','business','paid','original'}
    queue=[]
    for candidate in candidates:
        if candidate.get('eligible') is False:
            continue
        terms=set(re.findall(r'[a-z]+',candidate['name'].lower()))-ignored
        references=[]
        excluded=0
        for row in rows:
            if not terms.intersection(re.findall(r'[a-z]+',row[1].lower())):
                continue
            freshness = publication_freshness(row[2], now)
            if freshness in ('stale', 'future_date', 'invalid_date'):
                excluded += 1
                continue
            if len(references) < 3:
                references.append({'url':row[0], 'untrusted_title':row[1],
                                   'publisher_date':row[2], 'topic':row[3],
                                   'publication_freshness':freshness})
        # Missing/blocked sources must create a research task, not silently
        # remove the best candidate. This is a brief, never execution approval.
        queue.append({'model_id':candidate['id'], 'references':references,
                      'excluded_dated_references':excluded,
                      'status':'requires_demand_capability_and_economics_validation',
                      'next_action':'verify_current_sources' if references else 'find_current_primary_and_buyer_evidence',
                      'validation_requirements':[
                          'Compare at least two independent dated sources; separate vendor claims from buyer purchases and APEX results.',
                          'Record customer problem, current willingness to pay, acquisition access and competing offers.',
                          'Demonstrate an original deliverable; measure quality, delivery time, automation limits and reusable components.',
                          'Estimate price minus acquisition, tools, delivery labor, support, fees and refunds; label unknowns.',
                          'Define one bounded experiment, success metric, cost/time cap and stop rule; record results before scaling.',
                      ],
                      'external_actions_allowed':False})
        if len(queue)==2:break
    return queue


if __name__ == '__main__':
    print(json.dumps(run(os.environ.get('REVENUE_DB_PATH', '/files/data/revenue_agent.db'))))
