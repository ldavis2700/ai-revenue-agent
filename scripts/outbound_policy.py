#!/usr/bin/env python3
"""Evaluate whether a prospect is eligible for automated outreach on a channel."""
import argparse
import json


def allowed(payload):
    channel = str(payload.get('channel') or '').lower()
    consent = bool(payload.get('consent', False))
    contact_allowed = bool(payload.get('contact_allowed', False))
    opted_out = bool(payload.get('opted_out', False))
    suppressed = bool(payload.get('suppressed', False))
    if opted_out or suppressed:
        return False, 'suppressed_or_opted_out'
    if channel in {'sms', 'mms', 'whatsapp'}:
        if not consent:
            return False, 'explicit_consent_required'
        return True, 'consent_verified'
    if channel == 'email':
        if not contact_allowed:
            return False, 'source_not_approved_for_email_outreach'
        return True, 'approved_email_source'
    if channel in {'inbound', 'website', 'chat'}:
        return True, 'inbound_request'
    return False, 'unsupported_channel'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--json', required=True, help='Prospect/channel JSON payload')
    args = parser.parse_args()
    payload = json.loads(args.json)
    ok, reason = allowed(payload)
    print(json.dumps({'allowed': ok, 'reason': reason, 'channel': payload.get('channel')}))


if __name__ == '__main__':
    main()
