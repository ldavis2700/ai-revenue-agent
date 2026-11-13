"""Optional test Supabase handoff for fictional evidence-review; no remote writes by default."""
import argparse
import hashlib
import json
import os
import re
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import Request, HTTPRedirectHandler, build_opener
from research_evidence_demo import connect, evidence_hash

TABLE = 'apex_evidence_pilot_test'

def prepared_rows(db):
    """Recheck source binding and return only human-approved or corrected records."""
    rows = db.execute("""SELECT record_id,field_name,accepted_value,source_label,source_url,
      excerpt,evidence_sha256,review_status,reviewer FROM proposals ORDER BY record_id""").fetchall()
    out = []
    for row in rows:
        row = dict(row)
        if row['evidence_sha256'] != evidence_hash(row['source_label'], row['excerpt'], row['source_url']):
            raise ValueError('Evidence digest mismatch; refusing all exports')
        if row['review_status'] not in ('approved', 'corrected'):
            continue
        if not row['accepted_value'] or not row['reviewer']:
            raise ValueError('Reviewed row missing acceptance or reviewer')
        record = {key: row[key] for key in ('record_id', 'field_name', 'accepted_value',
            'source_label', 'source_url', 'evidence_sha256', 'review_status', 'reviewer')}
        blob = json.dumps(record, sort_keys=True, ensure_ascii=False, separators=(',', ':'))
        record['approval_key'] = hashlib.sha256(blob.encode('utf-8')).hexdigest()
        out.append(record)
    return out

def test_endpoint(origin):
    """Exact, dedicated project origin; fixed disposable table, never arbitrary endpoint."""
    if not isinstance(origin, str):
        raise ValueError('Missing Supabase test project origin')
    url = urlsplit(origin)
    if (url.scheme != 'https' or url.username or url.password or url.port
        or url.path not in ('', '/') or url.query or url.fragment
        or not re.fullmatch(r'[a-z0-9]{16,32}\.supabase\.co', url.netloc)):
        raise ValueError('Expected a dedicated HTTPS Supabase test project origin')
    return origin.rstrip('/') + '/rest/v1/' + TABLE + '?on_conflict=approval_key'

class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        return None

def send_test_rows(rows, origin, key, *, execute=False, confirmed=False):
    """HTTP acceptance is not proof of stored rows; readback is separate."""
    if not execute:
        return {'remote_requests': 0, 'api_accepted_rows': 0}
    if not confirmed:
        raise ValueError('Buyer-approved dedicated test project confirmation is required')
    if not isinstance(key, str) or not key.strip():
        raise ValueError('A secure test project API key is required')
    endpoint = test_endpoint(origin)
    if not rows:
        return {'remote_requests': 0, 'api_accepted_rows': 0}
    req = Request(endpoint, data=json.dumps(rows).encode('utf-8'), method='POST', headers={
        'apikey': key, 'Authorization': 'Bearer ' + key,
        'Content-Type': 'application/json', 'Prefer': 'resolution=ignore-duplicates,return=minimal'
    })
    try:
        with build_opener(NoRedirect).open(req, timeout=15) as response:
            status = response.status
    except Exception:
        raise ValueError('Test write request failed; no rows confirmed') from None
    if status not in (200, 201, 204):
        raise ValueError('Test write request not accepted')
    return {'remote_requests': 1, 'api_accepted_rows': len(rows),
        'note': 'HTTP acceptance only; independent buyer test-table readback still required'}

def run(db, *, execute=False, confirmed=False, origin=None, key=None):
    rows = prepared_rows(db)
    return {'prepared_approved_rows': len(rows),
        'prepared_approval_keys': [r['approval_key'] for r in rows],
        **send_test_rows(rows, origin, key, execute=execute, confirmed=confirmed)}

def main():
    parser = argparse.ArgumentParser(description='Offline-by-default evidence handoff to buyer test table')
    parser.add_argument('--db', required=True, type=Path)
    parser.add_argument('--test-project-url')
    parser.add_argument('--execute-test-write', action='store_true')
    parser.add_argument('--confirm-dedicated-test-project', action='store_true')
    options = parser.parse_args()
    with connect(options.db) as db:
        result = run(db, execute=options.execute_test_write,
          confirmed=options.confirm_dedicated_test_project,
          origin=options.test_project_url,
          key=os.environ.get('APEX_SUPABASE_TEST_API_KEY'))
    print(json.dumps(result, sort_keys=True, indent=2))

if __name__ == '__main__':
    main()
