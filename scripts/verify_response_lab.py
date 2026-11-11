#!/usr/bin/env python3
"""Read-only acceptance for the combined APEX academy/private-artifact release.

No deployment, payment, customer submission or publication is attempted. Run only
against the exact owned production origin or an isolated local loopback server.
Never pass tokens as command-line arguments or expose them in reports.
"""
import argparse
import json
import os
import re
from urllib.error import HTTPError, URLError
from urllib.request import Request, build_opener

from fetch_content_artifact import BASE_URL, NoRedirects, approved_origin

MAX_RESPONSE = 100_000
JOB_ID = re.compile(r'[a-z0-9][a-z0-9-]{2,79}\Z')


def get(origin, path, token=None):
    headers = {'Accept': 'application/json, text/html, text/css, application/javascript'}
    if token:
        headers['Authorization'] = 'Bearer ' + token
    request = Request(origin + path, headers=headers)
    opener = build_opener(NoRedirects())
    try:
        with opener.open(request, timeout=12) as response:
            if response.geturl() != origin + path:
                raise ValueError('unexpected redirect')
            return response.status, response.read(MAX_RESPONSE + 1), response.headers
    except HTTPError as error:
        try:
            return error.code, error.read(MAX_RESPONSE + 1), error.headers
        finally:
            error.close()


def inspect(origin, *, job_id=None, token=None):
    if not approved_origin(origin):
        raise ValueError('unapproved origin')
    if job_id is not None and not JOB_ID.fullmatch(job_id):
        raise ValueError('invalid job ID')
    if token is not None and (not token or '\r' in token or '\n' in token):
        raise ValueError('invalid bearer token')
    results = {}
    def require(label, path, status, marker=None):
        try:
            actual, body, headers = get(origin, path)
            valid = actual == status and len(body) <= MAX_RESPONSE
            if marker is not None:
                valid = valid and marker in body
            results[label] = {'ok': bool(valid), 'status': actual}
            return body if valid else b''
        except (URLError, OSError, ValueError) as error:
            results[label] = {'ok': False, 'error': type(error).__name__}
            return b''
    offer = require('offer', '/', 200, b'Online checkout is paused')
    academy = require('academy', '/academy', 200, b'APEX Response Lab')
    require('stylesheet', '/sales/academy.css', 200, b'.hero')
    require('builder', '/sales/academy.js', 200, b'apex-response-lab-progress-v1')
    require('privacy', '/privacy', 200, b'Privacy')
    health = require('health', '/health', 200, b'"healthy"')
    if health:
        try:
            value = json.loads(health)
            results['health']['ok'] &= (value.get('healthy') is True and
                                         'jobs' not in value and 'queue' in value)
        except (ValueError, TypeError):
            results['health']['ok'] = False
    if offer:
        results['offer']['ok'] &= b'buy.stripe.com' not in offer
    if academy:
        results['academy']['ok'] &= (b'buy.stripe.com' not in academy and
                                     b'Online checkout is paused' in academy)
    for label, path in [('source_denied', '/content_worker.py'),
                        ('database_denied', '/queue.db'),
                        ('env_denied', '/.env')]:
        require(label, path, 404)
    # A production release must not make private diagnostics anonymously public.
    code, body, _ = get(origin, '/admin/jobs')
    results['admin_denied'] = {'ok': code == 401 or code == 503, 'status': code}
    if job_id:
        path = '/artifacts/' + job_id + '/manifest.json'
        code, body, _ = get(origin, path)
        results['artifact_denied'] = {'ok': code in (401, 503), 'status': code}
        if token:
            code, body, headers = get(origin, path, token=token)
            valid = code == 200 and len(body) <= MAX_RESPONSE
            if valid:
                try:
                    manifest = json.loads(body)
                    # A successful HTTP 200 is not enough: reject incomplete or
                    # inconsistent published-manifest metadata before claiming
                    # private-artifact release acceptance. This validates the
                    # metadata shape, not the actual MP4 checksum.
                    digest = manifest.get('sha256') if isinstance(manifest, dict) else None
                    expected_bytes = manifest.get('bytes') if isinstance(manifest, dict) else None
                    valid = (isinstance(manifest, dict) and
                             manifest.get('id') == job_id and
                             manifest.get('status') == 'rendered_unpublished' and
                             type(expected_bytes) is int and 0 < expected_bytes <= 30_000_000 and
                             isinstance(digest, str) and
                             re.fullmatch(r'[0-9a-f]{64}', digest) is not None and
                             headers.get('Cache-Control') == 'private, no-store' and
                             headers.get_content_type() == 'application/json')
                except (ValueError, TypeError, AttributeError):
                    valid = False
            results['artifact_authorized'] = {'ok': bool(valid), 'status': code}
        else:
            results['artifact_authorized'] = {'ok': False, 'status': 'not_tested_missing_private_token'}
    else:
        results['artifact_authorized'] = {'ok': False, 'status': 'not_tested_missing_job_id'}
    return {'ready': all(v['ok'] for v in results.values()), 'checks': results}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--origin', required=True, help='Exact Railway origin or isolated loopback HTTP origin')
    parser.add_argument('--job-id', help='Known completed private job identifier for a manifest-only acceptance')
    args = parser.parse_args()
    result = inspect(args.origin, job_id=args.job_id,
                     token=os.environ.get('CONTENT_ARTIFACT_TOKEN') or None)
    print(json.dumps(result, sort_keys=True))
    raise SystemExit(0 if result['ready'] else 1)


if __name__ == '__main__':
    main()
