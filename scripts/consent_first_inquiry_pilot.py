"""Offline, human-reviewed inquiry triage demonstration; never sends messages.

All example inputs must be fictional. This is not a deployed sales workflow.
"""
from __future__ import annotations

from collections import Counter
import csv
from pathlib import Path
import re

REQUIRED = ('inquiry_id', 'email', 'message', 'consent_to_reply', 'opted_out', 'status')
EMAIL = re.compile(r'^[^\s@]+@[^\s@]+\.[^\s@]+$')
SAFE_ID = re.compile(r'^[A-Za-z0-9][A-Za-z0-9_-]{0,79}$')
COLUMNS = ('inquiry_id', 'decision', 'draft_reply', 'sent')
GENERIC_DRAFT = ('Thank you for your inquiry. A team member will review '
                 'your question and respond if appropriate.')


def allowed_reply(row: dict) -> bool:
    """True only for explicit consent, explicit non-opt-out, and new status."""
    return (str(row.get('consent_to_reply', '')).strip().lower() == 'true'
            and str(row.get('opted_out', '')).strip().lower() == 'false'
            and str(row.get('status', '')).strip().lower() == 'new'
            and bool(EMAIL.fullmatch(str(row.get('email', '')).strip())))


def process(input_csv: Path, output_csv: Path) -> dict:
    """Prepare review-only drafts; hold *every* occurrence of a duplicate ID.

    Input is read entirely before deciding eligibility so a late opt-out or
    contradictory duplicate cannot leave an earlier inquiry marked eligible.
    Only safe identifiers are exported; user-controlled text is never echoed.
    """
    with input_csv.open(newline='', encoding='utf-8-sig') as handle:
        reader = csv.DictReader(handle)
        if (not reader.fieldnames or len(reader.fieldnames) != len(set(reader.fieldnames))
                or not set(REQUIRED).issubset(reader.fieldnames)):
            raise ValueError('Required unique columns missing')
        rows = list(reader)

    identifiers = [str(row.get('inquiry_id') or '').strip() for row in rows]
    canonical = [identifier.casefold() for identifier in identifiers]
    counts = Counter(canonical)
    output = []
    for row, ident, key in zip(rows, identifiers, canonical):
        safe = bool(SAFE_ID.fullmatch(ident))
        if not safe or counts[key] != 1:
            decision = 'duplicate_or_invalid_id'
        elif not allowed_reply(row):
            decision = 'hold_no_consent_or_status'
        else:
            decision = 'human_review_required'
        output.append({
            'inquiry_id': ident if safe else '',
            'decision': decision,
            'draft_reply': GENERIC_DRAFT if decision == 'human_review_required' else '',
            'sent': 'false',
        })
    with output_csv.open('x', newline='', encoding='utf-8') as handle:
        writer = csv.DictWriter(handle, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(output)
    return {
        'review_items': len(output),
        'eligible_for_human_review': sum(item['decision'] == 'human_review_required' for item in output),
        'messages_sent': 0,
    }


if __name__ == '__main__':
    import argparse
    import json
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input', type=Path)
    parser.add_argument('output', type=Path)
    arguments = parser.parse_args()
    print(json.dumps(process(arguments.input, arguments.output), indent=2))

