"""Isolated, no-network paid preparation guard tests."""
import tempfile
from pathlib import Path
import hashlib
import unittest
from unittest.mock import patch
import json
import zipfile

from scripts.paid_preparation_consumer import (PreparationBlocked, make_archive,
                                               prepare_once, verified_setup)

EMAIL_HASH = hashlib.sha256(b"buyer@example.test").hexdigest()
PROFILE = {"company": "Example Cleaning", "services": "residential cleaning",
           "service_area": "Example City", "quote_process": "human review",
           "escalation_contact": "support team"}
DOSSIER = {"processor_event_id": "evt_sample123", "lead_id": "lead-one",
           "scope_accepted": True, "business_facts_verified": True,
           "scope_evidence_url": "https://example.test/private/scope",
           "profile": PROFILE}


class FakeGateway:
    def __init__(self):
        self.calls = []
        self.queue = []
        self.claim = []
        self.renew = True
        self.finish = True
        self.charge = {
            "id": "cs_sample123",
            "customer_details": {"email": "buyer@example.test"},
            "mode": "payment", "status": "complete", "payment_status": "paid",
            "metadata": {"apex_property_id": "003"},
            "amount_total": 10000, "currency": "usd",
            "payment_intent": {"id": "pi_sample123", "status": "succeeded", "amount_received": 10000,
                               "latest_charge": {"paid": True, "disputed": False,
                                                 "refunded": False, "amount_refunded": 0}}}

    def rows(self, table, **kwargs):
        self.calls.append(("rows", table))
        if table == "paid_fulfillment_queue":
            return self.queue
        if table == "verified_revenue_events":
            return [{"processor": "stripe", "revenue_kind": "one_time_checkout",
                     "amount_cents": 10000, "currency": "USD",
                     "source_object_id": "cs_sample123", "lead_id": "lead-one",
                     "customer_email_hash": EMAIL_HASH, "payment_reference": "pi_sample123"}]
        if table == "inbound_leads":
            return [{"id": "lead-one", "company_name": "Example Cleaning",
                     "email_hash": EMAIL_HASH}]
        raise AssertionError(table)

    def stripe_checkout(self, source_id):
        self.calls.append(("stripe", source_id))
        return self.charge

    def rpc(self, name, payload):
        self.calls.append(("rpc", name))
        if name == "claim_paid_preparation":
            return self.claim
        if name == "renew_paid_preparation":
            return self.renew
        if name == "finish_paid_preparation":
            return self.finish
        raise AssertionError(name)


class PreparationTests(unittest.TestCase):
    def test_empty_queue_never_claims(self):
        g = FakeGateway()
        with tempfile.TemporaryDirectory() as root:
            self.assertEqual(prepare_once(g, Path(root), Path(root)), "no_pending_obligations")
        self.assertEqual(g.calls, [("rows", "paid_fulfillment_queue")])

    def test_missing_dossier_never_claims(self):
        g = FakeGateway()
        g.queue = [{"processor_event_id": "evt_sample123", "work_kind": "setup"}]
        with tempfile.TemporaryDirectory() as root:
            with self.assertRaises(PreparationBlocked):
                prepare_once(g, Path(root), Path(root))
        self.assertNotIn(("rpc", "claim_paid_preparation"), g.calls)

    def test_wrong_price_refund_or_missing_scope_fails_before_claim(self):
        g = FakeGateway()
        for mutation in ("refund", "price", "scope"):
            dossier = dict(DOSSIER)
            g.charge["payment_intent"]["latest_charge"]["refunded"] = mutation == "refund"
            g.charge["amount_total"] = 10100 if mutation == "price" else 10000
            if mutation == "scope":
                dossier["scope_accepted"] = False
            with self.assertRaises(PreparationBlocked):
                verified_setup(g, "evt_sample123", dossier)
        self.assertNotIn(("rpc", "claim_paid_preparation"), g.calls)

    def test_full_pack_is_draft_only_and_hash_matches(self):
        with tempfile.TemporaryDirectory() as root:
            digest, archive = make_archive(PROFILE, Path(root), "worker-test")
            import hashlib
            self.assertEqual(hashlib.sha256(archive.read_bytes()).hexdigest(), digest)
            self.assertTrue((archive.parent / "manifest.json").is_file())
            with zipfile.ZipFile(archive) as bundle:
                manifest = json.loads(bundle.read("manifest.json"))
            self.assertFalse(manifest["delivery_verified"])
            self.assertFalse(manifest["buyer_acceptance_verified"])

    def test_current_lease_prepares_without_delivery(self):
        g = FakeGateway()
        g.queue = [{"processor_event_id": "evt_sample123", "work_kind": "setup"}]
        g.claim = [{"processor_event_id": "evt_sample123", "preparation_token": "token"}]
        with tempfile.TemporaryDirectory() as root:
            dossier_dir = Path(root) / "dossiers"
            archive_dir = Path(root) / "private"
            dossier_dir.mkdir()
            archive_dir.mkdir()
            import json
            (dossier_dir / "evt_sample123.json").write_text(json.dumps(DOSSIER))
            result = prepare_once(g, dossier_dir, archive_dir, worker="worker-test")
            self.assertEqual(result, "prepared_not_delivered")
            self.assertTrue((archive_dir / "worker-test" / "response-pack.zip").is_file())
        self.assertIn(("rpc", "renew_paid_preparation"), g.calls)
        self.assertIn(("rpc", "finish_paid_preparation"), g.calls)
        self.assertNotIn(("rpc", "block_paid_preparation"), g.calls)

    def test_false_finish_or_expired_lease_never_reports_success(self):
        for field in ("finish", "renew"):
            g = FakeGateway()
            g.queue = [{"processor_event_id": "evt_sample123", "work_kind": "setup"}]
            g.claim = [{"processor_event_id": "evt_sample123", "preparation_token": "token"}]
            setattr(g, field, False)
            with tempfile.TemporaryDirectory() as root:
                d, a = Path(root) / "d", Path(root) / "a"
                d.mkdir()
                a.mkdir()
                import json
                (d / "evt_sample123.json").write_text(json.dumps(DOSSIER))
                with self.assertRaises(RuntimeError):
                    prepare_once(g, d, a, worker="worker-test")


if __name__ == "__main__":
    unittest.main()
