"""Synthetic free-account evidence for tests; never use in production."""
from datetime import datetime, timedelta, timezone


def free_policy(endpoint, limit=20, now=None):
    now = now or datetime.now(timezone.utc)
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    return {
        'plan': 'free', 'provider': 'test-provider', 'account_id': 'test-account',
        'endpoint': endpoint, 'overage_behavior': 'hard_stop',
        'upfront_cost_cents': 0, 'recurring_cost_cents': 0, 'request_cost_cents': 0,
        'evidence_url': 'https://provider.example.test/account/free-plan-evidence',
        'verified_at': now.isoformat(), 'expires_at': (now + timedelta(hours=1)).isoformat(),
        'period_start': start.isoformat(), 'period_end': (start + timedelta(days=1)).isoformat(),
        'request_limit': limit,
    }
