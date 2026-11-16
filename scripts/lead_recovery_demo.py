"""Offline, no-send lead recovery demonstration. Python standard library only."""
import argparse
import csv
import io
import json
import re
from datetime import datetime, timezone
from pathlib import Path

MAX_RECORDS = 100
FIELDS = ('event_id', 'received_at', 'source', 'category', 'request_summary')
ALLOWED_SOURCES = {'web_form', 'inbox_notification', 'crm_webhook'}
# Fictional-only demo: block common contact/location link patterns before CSV or JSON export.
# Not a general PII detector; operators must never submit real customer records.
UNSAFE_SUMMARY = re.compile(
    r'@|https?://|www\.|(?<![A-Za-z0-9])\+?\d[\d\s().-]{7,}\d(?![A-Za-z0-9])',
    re.IGNORECASE,
)


def build_queue(records):
    """Create owner-review queue from fictional events; no send, networking, or stored state."""
    if not isinstance(records, list) or len(records) > MAX_RECORDS:
        raise ValueError('Input must be a list of at most 100 fictional events')
    seen, queue, rejected = set(), [], []
    for position, record in enumerate(records, 1):
        if not isinstance(record, dict) or any(not isinstance(record.get(k), str) for k in FIELDS):
            rejected.append({'position': position, 'reason': 'missing_or_invalid_fields'})
            continue
        event_id = record['event_id'].strip()
        if not re.fullmatch(r'[A-Za-z0-9_-]{1,50}', event_id):
            rejected.append({'position': position, 'reason': 'invalid_event_id'})
            continue
        if event_id in seen:
            rejected.append({'position': position, 'reason': 'duplicate_event'})
            continue
        if record['source'] not in ALLOWED_SOURCES or record['category'] not in {'quote', 'scheduling', 'general'}:
            rejected.append({'position': position, 'reason': 'unsupported_source_or_category'})
            continue
        try:
            stamp = datetime.fromisoformat(record['received_at'].replace('Z', '+00:00'))
            if stamp.tzinfo is None:
                raise ValueError('Timezone required')
        except ValueError:
            rejected.append({'position': position, 'reason': 'invalid_received_at'})
            continue
        summary = record['request_summary'].strip()
        if (not summary or len(summary) > 160 or UNSAFE_SUMMARY.search(summary)
                or any(ord(char) < 32 or ord(char) == 127 for char in summary)):
            rejected.append({'position': position, 'reason': 'unsafe_or_invalid_summary'})
            continue
        seen.add(event_id)
        queue.append({
            'inquiry_id': event_id,
            'received_at': stamp.astimezone(timezone.utc).isoformat(),
            'source': record['source'],
            'category': record['category'],
            'request_summary': summary,
            'review_status': 'owner_review_required',
            'draft_acknowledgment': 'Thank you for contacting us. Our team will review your inquiry and reply directly.',
            'customer_message_sent': False,
        })
    return {'mode': 'offline_fictional_demo', 'outbound_enabled': False,
            'accepted': len(queue), 'rejected': len(rejected), 'queue': queue, 'rejections': rejected}


def to_csv(report):
    output = io.StringIO()
    fields = ['inquiry_id', 'received_at', 'source', 'category', 'request_summary',
              'review_status', 'draft_acknowledgment', 'customer_message_sent']
    writer = csv.DictWriter(output, fieldnames=fields, lineterminator='\n')
    writer.writeheader()
    for row in report['queue']:
        safe = {k: ("'" + str(row[k]) if str(row[k]).startswith(('=', '+', '-', '@')) else row[k]) for k in fields}
        writer.writerow(safe)
    return output.getvalue()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, required=True, help='JSON fictional events; never use real customer data')
    parser.add_argument('--format', choices=('json', 'csv'), default='json')
    args = parser.parse_args()
    if args.input.stat().st_size > 32768:
        parser.error('Input too large')
    report = build_queue(json.loads(args.input.read_text(encoding='utf-8')))
    print(json.dumps(report, indent=2) if args.format == 'json' else to_csv(report), end='\n' if args.format == 'json' else '')


if __name__ == '__main__':
    main()
