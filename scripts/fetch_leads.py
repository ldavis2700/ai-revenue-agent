#!/usr/bin/env python3
"""Lead-source adapter for AI Revenue Agent.

Production behavior: read leads from LEADS_JSON or LEADS_API_URL.
No fake prospects are emitted unless ALLOW_SAMPLE_LEADS=true.
"""
import json
import os
import sys
import urllib.request


def fetch_leads():
    raw = os.getenv('LEADS_JSON')
    if raw:
        data = json.loads(raw)
        return data if isinstance(data, list) else data.get('leads', [])

    url = os.getenv('LEADS_API_URL')
    if url:
        req = urllib.request.Request(url, headers={'User-Agent': 'AI-Revenue-Agent/1.0'})
        token = os.getenv('LEADS_API_TOKEN')
        if token:
            req.add_header('Authorization', f'Bearer {token}')
        with urllib.request.urlopen(req, timeout=20) as response:
            data = json.loads(response.read().decode('utf-8'))
            return data if isinstance(data, list) else data.get('leads', [])

    if os.getenv('ALLOW_SAMPLE_LEADS', '').lower() == 'true':
        return [{
            'id': 'sample_001',
            'first_name': 'Sample',
            'company_name': 'Demo Local Business',
            'contact_email': 'owner@example.com',
            'industry': 'Local Services',
            'pain_point': 'slow follow-up on new inquiries',
            'contact_allowed': False,
            'source': 'sample'
        }]

    return []


if __name__ == '__main__':
    try:
        print(json.dumps(fetch_leads()))
    except Exception as exc:
        print(json.dumps({'error': str(exc)}))
        sys.exit(1)
