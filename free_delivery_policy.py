"""Enforce the owner's zero-spend rule before a delivery provider is called.

Configuration is an operator's time-limited record of verified provider terms,
not a billing API or permission to buy anything. Quota reservations are durable
and conservative: failed/ambiguous requests still consume a slot.
"""
import hashlib
import json
import os
from datetime import datetime, timedelta, timezone
from urllib.parse import urlsplit


def _time(value):
    parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if parsed.tzinfo is None:
        raise ValueError('timezone required')
    return parsed.astimezone(timezone.utc)


def _https(value):
    parsed = urlsplit(value)
    return (parsed.scheme == 'https' and parsed.hostname
            and not parsed.username and not parsed.password and not parsed.fragment)


def validate_policy(raw, endpoint, now=None):
    """Return a normalized free-only policy or a non-sensitive blocking reason."""
    now = now or datetime.now(timezone.utc)
    if not raw:
        return None, 'free_delivery_policy_required'
    try:
        policy = json.loads(raw)
        if not isinstance(policy, dict):
            raise ValueError('object required')
        if policy['plan'] != 'free' or policy['overage_behavior'] != 'hard_stop':
            return None, 'paid_or_overage_enabled_delivery_blocked'
        for key in ('upfront_cost_cents', 'recurring_cost_cents', 'request_cost_cents'):
            if type(policy[key]) is not int or policy[key] != 0:
                return None, 'nonzero_or_unknown_delivery_cost'
        if policy['endpoint'] != endpoint or not _https(endpoint):
            return None, 'delivery_cost_policy_endpoint_mismatch'
        if not _https(policy['evidence_url']):
            raise ValueError('evidence required')
        for key in ('provider', 'account_id'):
            if not isinstance(policy[key], str) or not policy[key].strip() or len(policy[key]) > 200:
                raise ValueError('account scope required')
        if type(policy['request_limit']) is not int or not 0 < policy['request_limit'] <= 1000000:
            raise ValueError('bounded quota required')
        verified, expires = _time(policy['verified_at']), _time(policy['expires_at'])
        start, end = _time(policy['period_start']), _time(policy['period_end'])
        if not (verified <= now < expires <= verified + timedelta(hours=24)):
            return None, 'free_delivery_evidence_expired_or_invalid'
        if not start <= now < end:
            return None, 'free_delivery_quota_period_inactive'
        account = json.dumps([policy['provider'].strip().lower(), policy['account_id'].strip()])
        return {
            'account_key': hashlib.sha256(account.encode()).hexdigest(),
            'period_start': start.isoformat(), 'period_end': end.isoformat(),
            'request_limit': policy['request_limit'],
        }, None
    except (ValueError, TypeError, KeyError, AttributeError, OverflowError):
        return None, 'invalid_free_delivery_policy'


def reserve_request(conn, endpoint, now=None):
    """Atomically reserve one free request, before any external side effect."""
    policy, reason = validate_policy(os.getenv('DELIVERY_FREE_TIER_POLICY_JSON', ''), endpoint, now)
    if reason:
        return False, reason
    try:
        conn.execute('BEGIN IMMEDIATE')
        conn.execute('''CREATE TABLE IF NOT EXISTS free_delivery_quota (
            account_key TEXT NOT NULL, period_start TEXT NOT NULL,
            period_end TEXT NOT NULL, request_limit INTEGER NOT NULL,
            requests_reserved INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY (account_key, period_start, period_end)
        )''')
        rows = conn.execute('''SELECT period_start, period_end, request_limit, requests_reserved
            FROM free_delivery_quota WHERE account_key=?
            AND period_start < ? AND period_end > ?''',
            (policy['account_key'], policy['period_end'], policy['period_start'])).fetchall()
        if rows:
            if len(rows) != 1 or tuple(rows[0][:3]) != (
                    policy['period_start'], policy['period_end'], policy['request_limit']):
                conn.rollback()
                return False, 'free_delivery_quota_conflict'
            if rows[0][3] >= policy['request_limit']:
                conn.rollback()
                return False, 'free_delivery_quota_exhausted'
        else:
            conn.execute('INSERT INTO free_delivery_quota VALUES (?,?,?,?,0)', (
                policy['account_key'], policy['period_start'], policy['period_end'], policy['request_limit']))
        conn.execute('''UPDATE free_delivery_quota SET requests_reserved=requests_reserved+1
            WHERE account_key=? AND period_start=? AND period_end=?''',
            (policy['account_key'], policy['period_start'], policy['period_end']))
        conn.commit()
        return True, 'free_request_reserved'
    except Exception:
        conn.rollback()
        raise
