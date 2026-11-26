import json
import os
import unittest
from datetime import datetime, timezone
from urllib.robotparser import RobotFileParser
from unittest.mock import patch

from scripts import public_market_research as r


class FranticDiscoveryTests(unittest.TestCase):
    def setUp(self):
        self.stamp = datetime(2026, 11, 26, tzinfo=timezone.utc).timestamp()
        self.date = '2026-11-25T00:00:00Z'
        self.robots = RobotFileParser()
        self.robots.parse(['User-agent: *', 'Allow: /'])
        self.calls = []

    def row(self, n=1, **overrides):
        return dict(number=n, price_usd=25, funded=True, visibility='public',
                    settled_at=None, claim_slots=dict(capacity=1, occupied=0, available=1),
                    api_url='https://evil.example/collect', **{}) | overrides

    def board(self, rows):
        return json.dumps(dict(ok=True, board=dict(open_bounties=rows))).encode()

    def detail(self, n, **overrides):
        return json.dumps(dict(ok=True, bounty=dict(
            number=n, funded=True, visibility='public', cancellation_status=None,
            price_cents=2500, claim_progress=dict(capacity=1, occupied=0, available=1),
            funded_receipt_ref='synthetic-reference', title='Example workflow audit',
            posted_at=self.date, funded_at=self.date, criteria={'example': True},
            delivery_contract={'format':'name=value'}, required_artifacts=['report']
        ) | overrides)).encode()

    def fetch(self, url):
        self.calls.append(url)
        return self.detail(int(url.rsplit('/', 1)[-1]))

    def test_opt_in_only(self):
        with patch.dict(os.environ, {'APEX_FRANTIC_DISCOVERY_ENABLED':'false'}):
            self.assertNotIn(r.FRANTIC_SOURCE, r.sources())
            with self.assertRaises(ValueError):
                r.fetch(r.FRANTIC_DETAIL+'1')

    def test_fixed_origin_dedup_and_bound(self):
        rows = [self.row(1), self.row(1)] + [self.row(n) for n in range(2, 9)]
        result = r.frantic_references(self.board(rows), self.fetch, self.robots, self.stamp)
        self.assertEqual(self.calls, [r.FRANTIC_DETAIL+str(n) for n in (1,2,3)])
        self.assertEqual(len(result), 3)
        self.assertNotIn('synthetic-reference', str(result))

    def test_invalid_board_rows_never_fetch(self):
        rows = [self.row(1, funded='true'), self.row(True),
                self.row(2, visibility='private'), self.row(3, price_usd=True),
                self.row(4, settled_at=self.date),
                self.row(5, claim_slots={'capacity':1,'occupied':1,'available':0})]
        self.assertEqual(r.frantic_references(self.board(rows), self.fetch, self.robots, self.stamp), [])
        self.assertEqual(self.calls, [])

    def test_missing_receipt_mismatch_cancelled_or_stale(self):
        for overrides in ({'funded_receipt_ref':None}, {'number':2},
                          {'price_cents':1}, {'cancellation_status':'cancelled'},
                          {'posted_at':'2020-01-01T00:00:00Z'}, {'funded':'true'}):
            with self.subTest(overrides=overrides):
                self.assertEqual(r.frantic_references(self.board([self.row()]),
                    lambda _: self.detail(1, **overrides), self.robots, self.stamp), [])

    def test_robots_denial(self):
        # RobotFileParser.parse appends rules; use a fresh policy for denial.
        self.robots = RobotFileParser()
        self.robots.parse(['User-agent: *', 'Disallow: /v1/bounties/'])
        self.assertFalse(self.robots.can_fetch(r.USER_AGENT, r.FRANTIC_DETAIL+'1'))
        self.assertEqual(r.frantic_references(self.board([self.row()]), self.fetch,
                                            self.robots, self.stamp), [])
        self.assertEqual(self.calls, [])

    def test_bad_payload(self):
        for body in (b'not JSON', b'{"ok":true,"board":{}}', b'x'*(r.MAX_BYTES+1)):
            with self.assertRaises(ValueError):
                r.frantic_references(body, self.fetch, self.robots, self.stamp)
