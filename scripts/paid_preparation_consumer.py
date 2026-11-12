#!/usr/bin/env python3
"""Supervised, server-only preparation of a verified APEX $100 setup obligation.

No sends, charges, delivery-state updates or background activation. The private
scope dossier must first be independently checked against the actual buyer.
Automatic managed-cycle fulfillment and delivery are deliberately unsupported.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
import uuid
import zipfile

from scripts.build_response_pack import validate_profile, write_pack

EVENT_RE = re.compile(r"evt_[A-Za-z0-9_]{3,120}\Z")
HEX_RE = re.compile(r"[a-f0-9]{64}\Z")
EXPECTED_FILES = ("response-pack.html", "response-use-guide.md",
                  "inquiry-tracker.csv", "manifest.json")
OWNED_SUPABASE_HOST = "wuzmqruxdclstezitsbf.supabase.co"


class RejectRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        raise PreparationBlocked("Authenticated request redirect refused")


class PreparationBlocked(RuntimeError):
    """Missing independent evidence: leave work pending and do not claim."""


class Transport:
    """Standard-library HTTP; never log credentials, bodies, or contact data."""

    def __init__(self, supabase_url, service_key, stripe_key):
        parsed = urllib.parse.urlsplit(supabase_url)
        if (parsed.scheme != "https" or parsed.hostname != OWNED_SUPABASE_HOST
                or parsed.path not in ("", "/") or parsed.query or parsed.fragment
                or parsed.username or parsed.password):
            raise ValueError("A valid HTTPS Supabase project origin is required")
        if not service_key or not stripe_key.startswith("sk_live_"):
            raise ValueError("Server-only service role and live Stripe secret required")
        self.origin = supabase_url.rstrip("/")
        self.service_key = service_key
        self.stripe_key = stripe_key

    @staticmethod
    def request(url, headers, data=None):
        request = urllib.request.Request(url, data=data, headers=headers,
                                         method="POST" if data is not None else "GET")
        with urllib.request.build_opener(RejectRedirect).open(request, timeout=20) as response:
            if response.status < 200 or response.status >= 300:
                raise PreparationBlocked("Upstream verification failed")
            return json.loads(response.read(131072))

    def rows(self, table, **filters):
        query = urllib.parse.urlencode(filters)
        headers = {"apikey": self.service_key,
                   "Authorization": "Bearer " + self.service_key}
        return self.request(self.origin + "/rest/v1/" + table + "?" + query, headers)

    def rpc(self, name, payload):
        headers = {"apikey": self.service_key,
                   "Authorization": "Bearer " + self.service_key,
                   "Content-Type": "application/json"}
        return self.request(self.origin + "/rest/v1/rpc/" + name, headers,
                            json.dumps(payload).encode("utf-8"))

    def stripe_checkout(self, source_id):
        if not re.fullmatch(r"cs_[A-Za-z0-9_]{3,150}", source_id or ""):
            raise PreparationBlocked("Missing valid Stripe Checkout source object")
        query = urllib.parse.urlencode({"expand[]": "payment_intent.latest_charge"})
        headers = {"Authorization": "Bearer " + self.stripe_key}
        return self.request("https://api.stripe.com/v1/checkout/sessions/"
                            + source_id + "?" + query, headers)


def one(rows, name):
    if not isinstance(rows, list) or len(rows) != 1 or not isinstance(rows[0], dict):
        raise PreparationBlocked("Missing or ambiguous " + name)
    return rows[0]


def verified_setup(gateway, event_id, dossier):
    """Verify current signed-ledger linkage and live Stripe payment, not settlement."""
    if not EVENT_RE.fullmatch(event_id or ""):
        raise PreparationBlocked("Invalid event identifier")
    if not isinstance(dossier, dict) or dossier.get("processor_event_id") != event_id:
        raise PreparationBlocked("Missing matching private buyer dossier")
    profile = validate_profile(dossier.get("profile"))
    if dossier.get("scope_accepted") is not True or dossier.get("business_facts_verified") is not True:
        raise PreparationBlocked("Buyer scope or business facts have not been verified")
    scope = dossier.get("scope_evidence_url")
    if not isinstance(scope, str) or not re.fullmatch(r"https://[^/@\s]+/[^\s]*", scope):
        raise PreparationBlocked("A private verifiable scope evidence URL is required")

    event = one(gateway.rows("verified_revenue_events", processor_event_id="eq." + event_id,
                             property_id="eq.003", select="*"), "APEX verified receipt")
    if (event.get("processor") != "stripe" or
            event.get("revenue_kind") != "one_time_checkout" or
            event.get("amount_cents") != 10000 or
            event.get("currency") != "USD" or not event.get("lead_id")):
        raise PreparationBlocked("Not a verified $100 APEX setup payment linked to a lead")
    if str(dossier.get("lead_id")) != str(event["lead_id"]):
        raise PreparationBlocked("Buyer dossier does not match verified lead identifier")
    lead = one(gateway.rows("inbound_leads", id="eq." + str(event["lead_id"]),
                            property_id="eq.003", select="id,company_name,email_hash"), "APEX buyer lead")
    if lead.get("company_name") != profile["company"]:
        raise PreparationBlocked("Business identity does not match approved buyer profile")
    email_hash = event.get("customer_email_hash")
    if (not isinstance(email_hash, str) or not HEX_RE.fullmatch(email_hash)
            or lead.get("email_hash") != email_hash):
        raise PreparationBlocked("Signed payment and buyer email hash do not match")
    checkout = gateway.stripe_checkout(event.get("source_object_id"))
    if checkout.get("id") != event.get("source_object_id"):
        raise PreparationBlocked("Stripe source object differs from signed receipt")
    customer_email = (checkout.get("customer_details") or {}).get("email")
    if (not isinstance(customer_email, str) or
            hashlib.sha256(customer_email.strip().lower().encode()).hexdigest() != email_hash):
        raise PreparationBlocked("Stripe payer email differs from verified lead")
    intent = checkout.get("payment_intent")
    if not isinstance(intent, dict) or intent.get("id") != event.get("payment_reference"):
        raise PreparationBlocked("PaymentIntent not independently matched")
    charge = intent.get("latest_charge")
    if not isinstance(charge, dict):
        raise PreparationBlocked("Charge not independently expanded")
    if (checkout.get("mode") != "payment" or checkout.get("status") != "complete"
            or checkout.get("payment_status") != "paid"
            or (checkout.get("metadata") or {}).get("apex_property_id") != "003"
            or checkout.get("amount_total") != 10000
            or (checkout.get("currency") or "").upper() != "USD"
            or intent.get("status") != "succeeded"
            or intent.get("amount_received") != 10000
            or charge.get("paid") is not True
            or charge.get("disputed") is not False
            or charge.get("refunded") is not False
            or charge.get("amount_refunded") != 0):
        raise PreparationBlocked("Current Stripe payment/refund/dispute check did not pass")
    return profile


def private_dossier(root, event_id):
    path = root / (event_id + ".json")
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 8192:
        raise PreparationBlocked("Private buyer dossier is missing or unsafe")
    return json.loads(path.read_text(encoding="utf-8"))


def make_archive(profile, root, worker):
    target = root / worker
    manifest = write_pack(profile, target)
    archive = target / "response-pack.zip"
    with zipfile.ZipFile(archive, "x", compression=zipfile.ZIP_DEFLATED) as bundle:
        for name in EXPECTED_FILES:
            info = zipfile.ZipInfo(name, date_time=(2020, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o600 << 16
            bundle.writestr(info, (target / name).read_bytes())
    if set(manifest["files"]) != set(EXPECTED_FILES) - {"manifest.json"}:
        raise RuntimeError("Incomplete pack manifest")
    with zipfile.ZipFile(archive) as bundle:
        if bundle.namelist() != list(EXPECTED_FILES):
            raise RuntimeError("Incomplete archive")
        for name, digest in manifest["files"].items():
            if hashlib.sha256(bundle.read(name)).hexdigest() != digest:
                raise RuntimeError("Archive content does not match manifest")
    # A verified private archive must reach the persistent filesystem before
    # its database checkpoint. The parent directory entry is fsynced as well.
    with archive.open("rb") as handle:
        os.fsync(handle.fileno())
    for directory in (target, root):
        fd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    if not HEX_RE.fullmatch(digest):
        raise RuntimeError("Bad artifact digest")
    return digest, archive


def prepare_once(gateway, dossiers, artifact_root, worker=None):
    """Never claim unless the current oldest eligible setup has all evidence."""
    candidates = gateway.rows("paid_fulfillment_queue", status="eq.pending",
                              prepared_at="is.null", order="created_at.asc,processor_event_id.asc",
                              select="processor_event_id,work_kind,preparation_expires_at,preparation_attempts",
                              limit="100")
    if not isinstance(candidates, list):
        raise RuntimeError("Could not read paid work queue")
    if not candidates:
        return "no_pending_obligations"
    # Active leases are not ours; an older worker may still own the obligation.
    from datetime import datetime, timezone
    def available(row):
        until = row.get("preparation_expires_at")
        if not until:
            return True
        return datetime.fromisoformat(until.replace("Z", "+00:00")) <= datetime.now(timezone.utc)
    eligible = [row for row in candidates
                if available(row) and int(row.get("preparation_attempts") or 0) < 5]
    if not eligible:
        return "no_claimable_preparation"
    first = eligible[0]
    if first.get("work_kind") != "setup":
        return "managed_cycle_needs_separate_authorized_fulfillment"
    event_id = first["processor_event_id"]
    dossier = private_dossier(dossiers, event_id)
    profile = verified_setup(gateway, event_id, dossier)
    worker = worker or ("apex-prep-" + uuid.uuid4().hex)
    if len(worker) > 128 or not re.fullmatch("[A-Za-z0-9_-]+", worker):
        raise ValueError("Invalid worker ID")
    claim = gateway.rpc("claim_paid_preparation", {"p_worker": worker, "p_lease_seconds": 600})
    if not isinstance(claim, list) or not claim:
        return "claim_lost_to_concurrent_worker"
    leased = one(claim, "preparation lease")
    if leased.get("processor_event_id") != event_id or not leased.get("preparation_token"):
        # Do not use a mismatched lease. Its bounded expiry permits recovery.
        raise RuntimeError("Claim changed between preflight and reservation")
    token = leased["preparation_token"]
    digest, archive = make_archive(profile, artifact_root, worker)
    if gateway.rpc("renew_paid_preparation", {"p_event_id": event_id,
            "p_token": token, "p_lease_seconds": 600}) is not True:
        raise RuntimeError("Lease expired; artifact preserved, no finish attempted")
    ref = archive.resolve().as_uri()
    try:
        finished = gateway.rpc("finish_paid_preparation", {
            "p_event_id": event_id, "p_token": token,
            "p_sha256": digest, "p_artifact_ref": ref})
    except (urllib.error.URLError, TimeoutError):
        # The finish may have committed: never replay without reconciliation.
        row = one(gateway.rows("paid_fulfillment_queue",
                    processor_event_id="eq." + event_id,
                    select="prepared_sha256,prepared_artifact_ref"), "preparation checkpoint")
        if row.get("prepared_sha256") == digest and row.get("prepared_artifact_ref") == ref:
            return "prepared_checkpoint_verified_after_timeout"
        raise RuntimeError("Uncertain finish; operator must reconcile")
    if finished is not True:
        raise RuntimeError("Finish returned false; no prepared success")
    return "prepared_not_delivered"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--dossier-root", type=Path, required=True)
    parser.add_argument("--artifact-root", type=Path, required=True)
    args = parser.parse_args()
    if not args.execute or os.environ.get("APEX_PAID_PREPARATION_ENABLED") != "true":
        parser.error("Supervised preparation is disabled; no claims made")
    repo = Path(__file__).resolve().parents[1]
    for p in (args.dossier_root, args.artifact_root):
        if not p.is_absolute() or p.is_symlink() or not p.is_dir() or p.resolve().is_relative_to(repo):
            parser.error("Existing private directories outside the repository are required")
        if p.stat().st_mode & 0o077:
            parser.error("Private directories must deny group/other access")
    if args.artifact_root.resolve() != Path("/data/private-paid-preparations"):
        parser.error("Artifacts must use /data/private-paid-preparations, not public content paths")
    gateway = Transport(os.environ.get("SUPABASE_URL", ""),
                        os.environ.get("SUPABASE_SERVICE_ROLE_KEY", ""),
                        os.environ.get("STRIPE_SECRET_KEY", ""))
    try:
        result = prepare_once(gateway, args.dossier_root, args.artifact_root)
    except (PreparationBlocked, ValueError) as exc:
        # Never print buyer profile, payment details, dossier, or credentials.
        print("preparation_not_claimed_or_completed: " + str(exc), file=sys.stderr)
        return 2
    print(result)
    return 0


if __name__ == "__main__":
    sys.exit(main())
